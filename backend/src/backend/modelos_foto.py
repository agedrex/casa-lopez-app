"""The photo of a model: storage and reading.

Same approach as the supplier documents (proveedores.py): the bytes live in the database, the type is decided by the file's
magic bytes (never by the declared mime or the extension) and the photo is served inline with `nosniff`. Only images are
accepted here (JPEG, PNG, WebP), never a PDF.

Rows are only added: a new upload is a new row and the newest row of a model is its current photo; the older ones stay as
history. The size limit is 5 MB, lower than the 10 MB of the supplier documents on purpose: a photo is shown on the page of
the model, and a phone camera photo over 5 MB is better resized than stored as is.
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from backend.models import FOTO_MIMES, Modelo, ModeloFoto
from backend.proveedores import ArchivoMuyGrande, detect_mime
from backend.servicios import DatosInvalidos, NoEncontrado, _insertar, _siguiente_numero

MAX_FOTO_BYTES = 5 * 1024 * 1024
MESSAGE_TOO_BIG = "La foto supera el máximo de 5 MB."
MESSAGE_FILE_TYPE = "El archivo no es una foto válida (se aceptan JPG, PNG o WebP)."
MESSAGE_EMPTY = "La foto está vacía."


def validate_photo(content: bytes) -> tuple[str, str]:
    """(mime, sha256) of an acceptable photo, or a Spanish refusal."""
    if len(content) > MAX_FOTO_BYTES:
        raise ArchivoMuyGrande(MESSAGE_TOO_BIG)
    if not content:
        raise DatosInvalidos(MESSAGE_EMPTY)
    mime = detect_mime(content)
    if mime not in FOTO_MIMES:
        raise DatosInvalidos(MESSAGE_FILE_TYPE)
    return mime, hashlib.sha256(content).hexdigest()


def add_photo(session: Session, codigo: str, *, contenido: bytes, subido_por: str) -> dict:
    """Stores a new photo for the model (a new row, the older ones are kept) and answers its data, without the bytes."""
    mime, digest = validate_photo(contenido)
    modelo = session.scalar(select(Modelo).where(Modelo.codigo == codigo))
    if modelo is None:
        raise NoEncontrado(f"No existe el modelo {codigo}.")
    fila = ModeloFoto(
        codigo=f"MFO-{_siguiente_numero(session, ModeloFoto.codigo, 'MFO'):04d}", modelo_id=modelo.id,
        contenido=contenido, tipo_mime=mime, sha256=digest, tamano_bytes=len(contenido), subido_por=subido_por,
    )
    _insertar(session, fila, "No se pudo asignar el código de la foto; intentá de nuevo.")
    session.commit()
    return {"codigo": fila.codigo, "modelo": modelo.codigo, "tipo_mime": mime, "tamano_bytes": len(contenido),
            "created_at": fila.created_at}


def get_photo(session: Session, codigo: str) -> tuple[bytes, str]:
    """(bytes, mime) of the newest photo of the model; `NoEncontrado` when it has none or the model does not exist."""
    fila = session.scalar(
        select(ModeloFoto).join(Modelo, Modelo.id == ModeloFoto.modelo_id).where(Modelo.codigo == codigo)
        .options(undefer(ModeloFoto.contenido)).order_by(ModeloFoto.id.desc()).limit(1)
    )
    if fila is None:
        raise NoEncontrado(f"El modelo {codigo} no tiene foto.")
    return bytes(fila.contenido), fila.tipo_mime
