"""Suppliers, what they charge for each material over time, and their documents (invoices, images): storage, the file
checks and the OCR states.

Files are stored in the database (bytea). The type is decided by the file's magic bytes, never by the declared mime or the
extension; the file name is sanitized and only ever used as a label. The OCR reads the file and stores plain text plus a
SUGGESTION of the number, date and total: it never fills the typed fields and never touches a price. The OCR text is untrusted:
it is stored and returned as plain text, and never put into HTML, SQL strings, logs or prompts.
"""

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, undefer

from backend.models import (
    DOCUMENT_TYPES, Color, DocumentoProveedor, Material, PedidoLinea, PedidoProveedor, PrecioMaterial, Proveedor,
)
from backend.ocr_llm import OcrError, OcrLLM, OcrResult, OcrSuggestion
from backend.servicios import (
    UNIQUE_VIOLATION, Conflicto, DatosInvalidos, NoEncontrado, _insertar, _patron, _siguiente_numero, _texto_o_nada,
    crear_precio, porcentaje_de_barra, variacion_de_precio,
)

# Audit lines go to uvicorn's logger. Only ids, sizes and outcome classes are logged: never the key, the file or its text.
logger = logging.getLogger("uvicorn.error")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_NUMBER_LENGTH = 60
SUPPLIER_CODE = re.compile(r"^PRV-[0-9]{4,}$")
MESSAGE_OCR_FAILED = "No se pudo leer el archivo ahora. Probá de nuevo más tarde."
MESSAGE_FILE_TYPE = "El archivo no es una foto ni un PDF válido (se aceptan JPG, PNG, WebP o PDF)."
MESSAGE_TOO_BIG = "El archivo supera el máximo de 10 MB."
MESSAGE_DUPLICATE_FILE = "Ese archivo ya está cargado para este proveedor."

_UNSAFE_NAME_CHARS = re.compile(r'[<>:"|?*]')
_MAX_NAME = 120
_MAX_EXTENSION = 10


class ArchivoMuyGrande(DatosInvalidos):
    """The file is over the size limit (HTTP 413)."""


# --- The file ----------------------------------------------------------------------------------------------------

def detect_mime(content: bytes) -> str | None:
    """The mime of a JPEG, PNG, WebP or PDF by its first bytes; None for anything else."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def validate_file(content: bytes) -> tuple[str, str]:
    """(mime, sha256) of an acceptable file, or a Spanish refusal. The size is checked before reading the bytes."""
    if len(content) > MAX_FILE_BYTES:
        raise ArchivoMuyGrande(MESSAGE_TOO_BIG)
    if not content:
        raise DatosInvalidos("El archivo está vacío.")
    mime = detect_mime(content)
    if mime is None:
        raise DatosInvalidos(MESSAGE_FILE_TYPE)
    return mime, hashlib.sha256(content).hexdigest()


def sanitize_filename(raw: str | None) -> str:
    """A short label: no directories, no control or invisible characters, no characters that break a header or a shell."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    name = "".join(char for char in name if unicodedata.category(char) not in ("Cc", "Cf"))
    name = _UNSAFE_NAME_CHARS.sub("_", re.sub(r"\s+", " ", name)).strip().lstrip(".").strip()
    if len(name) > _MAX_NAME:
        stem, dot, extension = name.rpartition(".")
        name = (stem[:_MAX_NAME - len(extension) - 1] + dot + extension) if dot and len(extension) <= _MAX_EXTENSION \
            else name[:_MAX_NAME]
    return name or "archivo"


def file_headers(mime: str, filename: str) -> dict[str, str]:
    """Headers to serve a stored file: images open inline, PDFs download, and the browser must not guess the type."""
    label = sanitize_filename(filename)
    fallback = re.sub(r"[^A-Za-z0-9._ -]", "_", label)
    disposition = "inline" if mime.startswith("image/") else "attachment"
    return {
        "Content-Disposition": f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(label, safe='')}",
        "X-Content-Type-Options": "nosniff",
        # Defense in depth: even an inline file cannot run anything or load anything.
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, no-store",
    }


def validate_amounts(total: Decimal | None, currency: str | None) -> None:
    if total is not None and total < 0:
        raise DatosInvalidos("El total no puede ser negativo.")
    if total is not None and currency is None:
        raise DatosInvalidos("Si cargás un total, indicá la moneda (ARS o USD).")


def _clean_number(value: str | None) -> str | None:
    cleaned = _texto_o_nada((value or "").replace("\x00", ""))
    if cleaned is not None and len(cleaned) > MAX_NUMBER_LENGTH:
        raise DatosInvalidos(f"El número del documento no puede tener más de {MAX_NUMBER_LENGTH} caracteres.")
    return cleaned


# --- OCR ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class OcrOutcome:
    state: str  # LISTO, ERROR or NO_CONFIGURADO
    error: str | None = None
    result: OcrResult | None = None


def read_ocr(ocr: OcrLLM | None, content: bytes, mime: str) -> OcrOutcome:
    """Run the reader. It never raises: a failure is an outcome with a safe message, and the file is never lost."""
    if ocr is None:
        return OcrOutcome("NO_CONFIGURADO")
    try:
        return OcrOutcome("LISTO", result=ocr.read(content, mime))
    except OcrError as error:
        return OcrOutcome("ERROR", error=error.message)
    except Exception as error:  # noqa: BLE001 - the stored message must never carry the raw error (it may hold the key)
        logger.warning("proveedores ocr fallo inesperado: %s", type(error).__name__)
        return OcrOutcome("ERROR", error=MESSAGE_OCR_FAILED)


def _suggestion_json(suggestion: OcrSuggestion) -> dict:
    return {
        "numero": suggestion.numero,
        "fecha": suggestion.fecha.isoformat() if suggestion.fecha else None,
        "total": format(suggestion.total, "f") if suggestion.total is not None else None,
        "moneda": suggestion.moneda,
    }


def apply_outcome(document: DocumentoProveedor, outcome: OcrOutcome) -> None:
    """Store an outcome. A failed read keeps what an earlier good read stored; the typed fields are never touched."""
    document.ocr_estado = outcome.state
    document.ocr_error = outcome.error
    if outcome.result is not None:
        # Postgres text cannot hold NUL; the rest of the text is kept verbatim, as plain text.
        document.ocr_texto = outcome.result.text.replace("\x00", "")
        document.ocr_sugerencia = _suggestion_json(outcome.result.suggestion)


def apply_ocr(document: DocumentoProveedor, ocr: OcrLLM | None) -> None:
    apply_outcome(document, read_ocr(ocr, document.contenido, document.mime))


# --- Suppliers ---------------------------------------------------------------------------------------------------

def _supplier(session: Session, code: str) -> Proveedor:
    supplier = session.scalar(select(Proveedor).where(Proveedor.codigo == code))
    if supplier is None:
        raise NoEncontrado(f"No existe el proveedor {code}.")
    return supplier


def _supplier_to_dict(supplier: Proveedor, documents: int) -> dict:
    return {
        "codigo": supplier.codigo, "nombre": supplier.nombre, "cuit": supplier.cuit, "contacto": supplier.contacto,
        "telefono": supplier.telefono, "direccion": supplier.direccion, "nota": supplier.nota, "activo": supplier.activo,
        "documentos": documents,
    }


def _document_count(session: Session, supplier_id: int) -> int:
    return session.scalar(select(func.count(DocumentoProveedor.id)).where(DocumentoProveedor.proveedor_id == supplier_id)) or 0


def list_suppliers(session: Session, q: str | None = None, activo: bool | None = None) -> list[dict]:
    """Every word of `q` must appear in the code, name, CUIT, contact, phone or address."""
    counts = func.count(DocumentoProveedor.id)
    query = (select(Proveedor, counts).outerjoin(DocumentoProveedor, DocumentoProveedor.proveedor_id == Proveedor.id)
             .group_by(Proveedor.id).order_by(Proveedor.id))
    for word in (q or "").split():
        pattern = _patron(word)
        query = query.where(or_(*(column.ilike(pattern, escape="\\") for column in (
            Proveedor.codigo, Proveedor.nombre, Proveedor.cuit, Proveedor.contacto, Proveedor.telefono,
            Proveedor.direccion))))
    if activo is not None:
        query = query.where(Proveedor.activo.is_(activo))
    return [_supplier_to_dict(supplier, documents) for supplier, documents in session.execute(query).all()]


def get_supplier(session: Session, code: str) -> dict:
    supplier = _supplier(session, code)
    return _supplier_to_dict(supplier, _document_count(session, supplier.id))


def _check_unique_data(session: Session, name: str, cuit: str | None, *, own_id: int | None = None) -> None:
    same_name = select(Proveedor.id).where(func.lower(Proveedor.nombre) == func.lower(name))
    if own_id is not None:
        same_name = same_name.where(Proveedor.id != own_id)
    if session.scalar(same_name):
        raise Conflicto(f"Ya hay un proveedor con el nombre {name}.")
    if cuit:
        same_cuit = select(Proveedor.id).where(Proveedor.cuit == cuit)
        if own_id is not None:
            same_cuit = same_cuit.where(Proveedor.id != own_id)
        if session.scalar(same_cuit):
            raise Conflicto(f"Ya hay un proveedor con el CUIT {cuit}.")


def _flush_or_conflict(session: Session, message: str) -> None:
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise Conflicto(message) from None
        raise DatosInvalidos("Los datos no cumplen las reglas de la base.") from None


_DUPLICATE_SUPPLIER = "Ya hay un proveedor con ese nombre, ese CUIT o ese código; intentá de nuevo."


def create_supplier(
    session: Session, *, codigo: str | None, nombre: str, cuit: str | None, contacto: str | None, telefono: str | None,
    direccion: str | None, nota: str | None,
) -> dict:
    name = nombre.strip()
    cuit = _texto_o_nada(cuit)
    if not name:
        raise DatosInvalidos("Falta el nombre del proveedor.")
    _check_unique_data(session, name, cuit)
    if codigo is not None:
        # SUPUESTO: validar. PRV-NNNN matches the codes `precio_material.proveedor` holds from the external supplier file;
        # the next number only looks at this table, so an explicit code is the way to keep the two files aligned.
        if not SUPPLIER_CODE.match(codigo):
            raise DatosInvalidos("El código del proveedor tiene que ser PRV- y al menos cuatro números (por ejemplo PRV-0001).")
        if session.scalar(select(Proveedor.id).where(Proveedor.codigo == codigo)):
            raise Conflicto(f"Ya hay un proveedor con el código {codigo}.")
    code = codigo or f"PRV-{_siguiente_numero(session, Proveedor.codigo, 'PRV'):04d}"
    row = Proveedor(
        codigo=code, nombre=name, cuit=cuit, contacto=_texto_o_nada(contacto), telefono=_texto_o_nada(telefono),
        direccion=_texto_o_nada(direccion), nota=_texto_o_nada(nota),
    )
    _insertar(session, row, _DUPLICATE_SUPPLIER)
    session.commit()
    return get_supplier(session, code)


def update_supplier(
    session: Session, code: str, *, nombre: str, cuit: str | None, contacto: str | None, telefono: str | None,
    direccion: str | None, nota: str | None,
) -> dict:
    """Edit the data of a supplier (the code never changes). Every field is replaced by what the form sends."""
    supplier = _supplier(session, code)
    name = nombre.strip()
    cuit = _texto_o_nada(cuit)
    if not name:
        raise DatosInvalidos("Falta el nombre del proveedor.")
    _check_unique_data(session, name, cuit, own_id=supplier.id)
    supplier.nombre, supplier.cuit = name, cuit
    supplier.contacto, supplier.telefono = _texto_o_nada(contacto), _texto_o_nada(telefono)
    supplier.direccion, supplier.nota = _texto_o_nada(direccion), _texto_o_nada(nota)
    _flush_or_conflict(session, _DUPLICATE_SUPPLIER)
    session.commit()
    return get_supplier(session, code)


def set_supplier_active(session: Session, code: str, activo: bool) -> dict:
    """Archiving hides nothing and deletes nothing: the documents of the supplier stay."""
    _supplier(session, code).activo = activo
    session.commit()
    return get_supplier(session, code)


# --- Documents ---------------------------------------------------------------------------------------------------

def _document_to_dict(document: DocumentoProveedor, supplier_code: str) -> dict:
    """Everything but the file itself."""
    return {
        "id": document.id, "proveedor": supplier_code, "tipo": document.tipo, "nombre_archivo": document.nombre_archivo,
        "mime": document.mime, "tamano_bytes": document.tamano_bytes, "sha256": document.sha256,
        "numero": document.numero, "fecha_documento": document.fecha_documento, "total": document.total,
        "moneda": document.moneda, "ocr_estado": document.ocr_estado, "ocr_texto": document.ocr_texto,
        "ocr_sugerencia": document.ocr_sugerencia, "ocr_error": document.ocr_error, "subido_por": document.subido_por,
        "created_at": document.created_at,
    }


def _document(session: Session, document_id: int, *, with_content: bool = False) -> tuple[DocumentoProveedor, str]:
    query = (select(DocumentoProveedor, Proveedor.codigo).join(Proveedor, Proveedor.id == DocumentoProveedor.proveedor_id)
             .where(DocumentoProveedor.id == document_id))
    if with_content:
        query = query.options(undefer(DocumentoProveedor.contenido))
    row = session.execute(query).one_or_none()
    if row is None:
        raise NoEncontrado(f"No existe el documento {document_id}.")
    return row[0], row[1]


def list_documents(session: Session, code: str, q: str | None = None) -> list[dict]:
    """Newest first. Every word of `q` must appear in the file name, the number or the OCR text (case-insensitive).

    The file itself (`contenido`) is deferred and never loaded here.
    """
    supplier = _supplier(session, code)
    query = select(DocumentoProveedor).where(DocumentoProveedor.proveedor_id == supplier.id)
    for word in (q or "").split():
        pattern = _patron(word)
        query = query.where(or_(*(column.ilike(pattern, escape="\\") for column in (
            DocumentoProveedor.nombre_archivo, DocumentoProveedor.numero, DocumentoProveedor.ocr_texto))))
    return [_document_to_dict(document, supplier.codigo)
            for document in session.scalars(query.order_by(DocumentoProveedor.id.desc()))]


def add_document(
    session: Session, code: str, *, contenido: bytes, nombre_archivo: str | None, tipo: str, numero: str | None,
    fecha_documento: date | None, total: Decimal | None, moneda: str | None, subido_por: str, ocr: OcrLLM | None,
) -> dict:
    """Store the file first (so an OCR failure never loses it), then read it. The typed fields are the person's."""
    supplier = _supplier(session, code)
    if tipo not in DOCUMENT_TYPES:
        raise DatosInvalidos("El tipo de documento tiene que ser factura, imagen u otro.")
    mime, digest = validate_file(contenido)
    validate_amounts(total, moneda)
    if session.scalar(select(DocumentoProveedor.id).where(
            DocumentoProveedor.proveedor_id == supplier.id, DocumentoProveedor.sha256 == digest)):
        raise Conflicto(MESSAGE_DUPLICATE_FILE)
    row = DocumentoProveedor(
        proveedor_id=supplier.id, tipo=tipo, nombre_archivo=sanitize_filename(nombre_archivo), mime=mime,
        tamano_bytes=len(contenido), sha256=digest, contenido=contenido, numero=_clean_number(numero),
        fecha_documento=fecha_documento, total=total, moneda=moneda, ocr_estado="PENDIENTE", subido_por=subido_por,
    )
    _insertar(session, row, MESSAGE_DUPLICATE_FILE)
    session.commit()
    # The network call runs with no pending write: only the outcome is stored afterwards.
    outcome = read_ocr(ocr, contenido, mime)
    document, supplier_code = _document(session, row.id)
    apply_outcome(document, outcome)
    session.commit()
    return _document_to_dict(document, supplier_code)


def get_file(session: Session, document_id: int) -> tuple[bytes, str, str]:
    """(bytes, mime, file name) of a stored document."""
    document, _ = _document(session, document_id, with_content=True)
    return bytes(document.contenido), document.mime, document.nombre_archivo


def retry_ocr(session: Session, document_id: int, *, ocr: OcrLLM | None) -> dict:
    document, _ = _document(session, document_id, with_content=True)
    content, mime = bytes(document.contenido), document.mime
    session.commit()  # nothing pending: this only closes the transaction before the network call
    outcome = read_ocr(ocr, content, mime)
    document, supplier_code = _document(session, document_id)
    apply_outcome(document, outcome)
    session.commit()
    return _document_to_dict(document, supplier_code)


def confirm_document_data(
    session: Session, document_id: int, *, tipo: str, numero: str | None, fecha_documento: date | None,
    total: Decimal | None, moneda: str | None,
) -> dict:
    """The only update of a stored document: what a person typed or confirmed. The file and the OCR are never touched."""
    document, supplier_code = _document(session, document_id)
    if tipo not in DOCUMENT_TYPES:
        raise DatosInvalidos("El tipo de documento tiene que ser factura, imagen u otro.")
    validate_amounts(total, moneda)
    document.tipo = tipo
    document.numero = _clean_number(numero)
    document.fecha_documento = fecha_documento
    document.total = total
    document.moneda = moneda
    session.commit()
    return _document_to_dict(document, supplier_code)


# --- What a supplier charges: materials and the history of their prices -------------------------------------------
# The prices live in `precio_material` (append-only). A price belongs to a supplier through `proveedor_id`; a row that was
# loaded before the link existed still counts when its text is exactly the supplier's code (codes are unique).

@dataclass(frozen=True)
class PrecioDeProveedor:
    id: int
    codigo: str
    material_id: int
    material: str
    material_nombre: str
    color_id: int | None
    color: str | None
    precio: Decimal
    moneda: str
    unidad_del_precio: str
    iva_incluido: bool
    vigente_desde: date
    nota_fuente: str | None


def _serie_de_precios(precios: list[PrecioDeProveedor]) -> dict:
    """One material (and color) of one supplier. The variation compares each price with the previous one in the same currency."""
    cronologico = sorted(precios, key=lambda p: (p.vigente_desde, p.id))
    anterior_por_moneda: dict[str, Decimal] = {}
    entradas = []
    for precio in cronologico:
        variacion, salto = variacion_de_precio(anterior_por_moneda.get(precio.moneda), precio.precio)
        anterior_por_moneda[precio.moneda] = precio.precio
        entradas.append({
            "codigo": precio.codigo, "vigente_desde": precio.vigente_desde, "precio": precio.precio, "moneda": precio.moneda,
            "unidad_del_precio": precio.unidad_del_precio, "iva_incluido": precio.iva_incluido,
            "nota_fuente": precio.nota_fuente, "variacion_pct": variacion, "salto_grande": salto,
        })
    maximo_por_moneda: dict[str, Decimal] = {}
    for entrada in entradas:
        maximo_por_moneda[entrada["moneda"]] = max(maximo_por_moneda.get(entrada["moneda"], entrada["precio"]), entrada["precio"])
    for entrada in entradas:  # bars only compare prices in the same currency
        entrada["barra_pct"] = porcentaje_de_barra(entrada["precio"], maximo_por_moneda[entrada["moneda"]])
    ultimo = entradas[-1]
    primero_ultimo = variacion_de_precio(entradas[0]["precio"], ultimo["precio"])[0] \
        if len(entradas) > 1 and entradas[0]["moneda"] == ultimo["moneda"] else None
    muestra = cronologico[0]
    return {
        "material": muestra.material, "material_nombre": muestra.material_nombre, "color": muestra.color,
        "ultimo_precio": ultimo["precio"], "moneda": ultimo["moneda"], "unidad_del_precio": ultimo["unidad_del_precio"],
        "ultima_fecha": ultimo["vigente_desde"], "variacion_ultima_pct": ultimo["variacion_pct"],
        "variacion_total_pct": primero_ultimo, "cargas": len(entradas), "historial": entradas[::-1],
    }


def materiales_de_proveedor(precios: list[PrecioDeProveedor]) -> list[dict]:
    """Group the prices of one supplier by material and color; materials A to Z, the plain color before the colored ones."""
    series: dict[tuple[int, int | None], list[PrecioDeProveedor]] = {}
    for precio in precios:
        series.setdefault((precio.material_id, precio.color_id), []).append(precio)
    ordenadas = sorted(series.values(), key=lambda lista: (lista[0].material_nombre.lower(), lista[0].color or ""))
    return [_serie_de_precios(lista) for lista in ordenadas]


def _prices_of(session: Session, supplier: Proveedor) -> list[PrecioDeProveedor]:
    linked = or_(PrecioMaterial.proveedor_id == supplier.id,
                 and_(PrecioMaterial.proveedor_id.is_(None), PrecioMaterial.proveedor == supplier.codigo))
    rows = session.execute(
        select(PrecioMaterial, Material.codigo, Material.nombre, Color.nombre)
        .join(Material, Material.id == PrecioMaterial.material_id)
        .outerjoin(Color, Color.id == PrecioMaterial.color_id)
        .where(linked)
    ).all()
    return [PrecioDeProveedor(
        id=p.id, codigo=p.codigo, material_id=p.material_id, material=material, material_nombre=nombre,
        color_id=p.color_id, color=color, precio=p.precio, moneda=p.moneda, unidad_del_precio=p.unidad_del_precio,
        iva_incluido=p.iva_incluido, vigente_desde=p.vigente_desde, nota_fuente=p.nota_fuente,
    ) for p, material, nombre, color in rows]


def list_supplier_materials(session: Session, code: str) -> dict:
    supplier = _supplier(session, code)
    return {"proveedor": supplier.codigo, "proveedor_nombre": supplier.nombre,
            "materiales": materiales_de_proveedor(_prices_of(session, supplier))}


def add_supplier_price(
    session: Session, code: str, *, material: str, color: str | None, precio: Decimal, moneda: str,
    unidad_del_precio: str, iva_incluido: bool, vigente_desde: date, nota_fuente: str | None,
) -> dict:
    """A new price of a material from this supplier: a new dated row linked to it, never an edit of an older one.

    The same rules as `POST /precios` apply (unit equal to the consumption unit, one price per material, color and date).
    SUPUESTO: validar. Like any price, from its date on it is the one the costs use for that material.
    """
    supplier = _supplier(session, code)
    return crear_precio(
        session, material=material, color=color, proveedor=supplier.codigo, proveedor_id=supplier.id, precio=precio,
        moneda=moneda, unidad_del_precio=unidad_del_precio, iva_incluido=iva_incluido, vigente_desde=vigente_desde,
        nota_fuente=_texto_o_nada(nota_fuente),
    )


# --- Orders: what arrived from a supplier, how it came, and the price each line creates ---------------------------
# An order is append-only (a correction is a new order). Saving it creates one `precio_material` row per line through
# `crear_precio`, all inside one transaction: if any line fails, no order and no price is stored.

MAX_PRESENTATION = 60
MAX_ORDER_TEXT = 500
# SUPUESTO: validar. The unit price is kept with the precision of `money()` (4 decimals), rounded half up.
UNIT_PRICE_STEP = Decimal("0.0001")


def unit_price(price_per_presentation: Decimal, content_per_presentation: Decimal) -> Decimal:
    """Price of one consumption unit of the material: what a presentation costs divided by what it holds."""
    return (price_per_presentation / content_per_presentation).quantize(UNIT_PRICE_STEP, rounding=ROUND_HALF_UP)


def _order_to_dict(order: PedidoProveedor, supplier_code: str, lines: list[tuple]) -> dict:
    return {
        "codigo": order.codigo, "proveedor": supplier_code, "fecha_de_recepcion": order.fecha_de_recepcion,
        "remito": order.remito, "documento_id": order.documento_id, "nota": order.nota, "creado_por": order.creado_por,
        "created_at": order.created_at,
        "lineas": [{
            "orden": line.orden, "material": material, "material_nombre": name, "unidad_de_consumo": unit,
            "cantidad_presentaciones": line.cantidad_presentaciones, "presentacion": line.presentacion,
            "contenido_por_presentacion": line.contenido_por_presentacion,
            "precio_por_presentacion": line.precio_por_presentacion, "moneda": line.moneda,
            "iva_incluido": line.iva_incluido, "precio_unitario": price.precio, "precio_codigo": price.codigo,
        } for line, material, name, unit, price in lines],
    }


def _order_lines(session: Session, order_ids: list[int]) -> dict[int, list[tuple]]:
    rows = session.execute(
        select(PedidoLinea, Material.codigo, Material.nombre, Material.unidad_de_consumo, PrecioMaterial)
        .join(Material, Material.id == PedidoLinea.material_id)
        .join(PrecioMaterial, PrecioMaterial.id == PedidoLinea.precio_material_id)
        .where(PedidoLinea.pedido_id.in_(order_ids)).order_by(PedidoLinea.pedido_id, PedidoLinea.orden)
    ).all()
    lines: dict[int, list[tuple]] = {}
    for row in rows:
        lines.setdefault(row[0].pedido_id, []).append(row)
    return lines


def list_orders(session: Session, code: str) -> list[dict]:
    """The orders of a supplier, newest reception first, each with its lines and the unit price it created."""
    supplier = _supplier(session, code)
    orders = session.scalars(
        select(PedidoProveedor).where(PedidoProveedor.proveedor_id == supplier.id)
        .order_by(PedidoProveedor.fecha_de_recepcion.desc(), PedidoProveedor.id.desc())).all()
    lines = _order_lines(session, [order.id for order in orders])
    return [_order_to_dict(order, supplier.codigo, lines.get(order.id, [])) for order in orders]


def _line_error(error: Exception, position: int, material: str) -> Exception:
    """The same kind of error with the line it came from, so the person knows what to fix."""
    return type(error)(f"Línea {position} ({material}): {error}")


def create_order(
    session: Session, code: str, *, fecha_de_recepcion: date, remito: str | None, documento_id: int | None,
    nota: str | None, lineas: list[dict], creado_por: str,
) -> dict:
    """Store an order and, for each line, the price it implies. All or nothing."""
    supplier = _supplier(session, code)
    if not lineas:
        raise DatosInvalidos("El pedido necesita al menos una línea.")
    if documento_id is not None and session.scalar(select(DocumentoProveedor.id).where(
            DocumentoProveedor.id == documento_id, DocumentoProveedor.proveedor_id == supplier.id)) is None:
        raise DatosInvalidos(f"El documento {documento_id} no existe o no es de este proveedor.")
    clean_lines = []
    for position, line in enumerate(lineas, start=1):
        presentation = (line["presentacion"] or "").strip()
        if not presentation:
            raise DatosInvalidos(f"Línea {position} ({line['material']}): falta la presentación.")
        clean_lines.append({**line, "presentacion": presentation})
    # One savepoint around the whole order: any failure below undoes the order and every price already flushed.
    with session.begin_nested():
        order = PedidoProveedor(
            codigo=f"PED-{_siguiente_numero(session, PedidoProveedor.codigo, 'PED'):04d}", proveedor_id=supplier.id,
            fecha_de_recepcion=fecha_de_recepcion, remito=_texto_o_nada(remito), documento_id=documento_id,
            nota=_texto_o_nada(nota), creado_por=creado_por,
        )
        _insertar(session, order, "No se pudo asignar el código del pedido; intentá de nuevo.")
        for position, line in enumerate(clean_lines, start=1):
            _add_order_line(session, supplier, order, position, line)
    session.commit()
    return _stored_order(session, supplier, order.id)


def _stored_order(session: Session, supplier: Proveedor, order_id: int) -> dict:
    order = session.get(PedidoProveedor, order_id)
    return _order_to_dict(order, supplier.codigo, _order_lines(session, [order_id]).get(order_id, []))


def _add_order_line(session: Session, supplier: Proveedor, order: PedidoProveedor, position: int, line: dict) -> None:
    material = session.scalar(select(Material).where(Material.codigo == line["material"]))
    if material is None:
        raise DatosInvalidos(f"Línea {position} ({line['material']}): no existe el material {line['material']}.")
    price = unit_price(line["precio_por_presentacion"], line["contenido_por_presentacion"])
    try:
        # SUPUESTO: validar. The price applies to every colour of the material (colour NULL), like a supplier price.
        created = crear_precio(
            session, material=material.codigo, color=None, proveedor=supplier.codigo, proveedor_id=supplier.id,
            precio=price, moneda=line["moneda"], unidad_del_precio=material.unidad_de_consumo,
            iva_incluido=line["iva_incluido"], vigente_desde=order.fecha_de_recepcion,
            nota_fuente=f"Pedido {order.codigo}", commit=False,
        )
    except (DatosInvalidos, Conflicto) as error:
        raise _line_error(error, position, material.codigo) from None
    price_id = session.scalar(select(PrecioMaterial.id).where(PrecioMaterial.codigo == created["codigo"]))
    _insertar(session, PedidoLinea(
        pedido_id=order.id, orden=position, material_id=material.id,
        cantidad_presentaciones=line["cantidad_presentaciones"], presentacion=line["presentacion"],
        contenido_por_presentacion=line["contenido_por_presentacion"],
        precio_por_presentacion=line["precio_por_presentacion"], moneda=line["moneda"],
        iva_incluido=line["iva_incluido"], precio_material_id=price_id,
    ), f"Línea {position} ({material.codigo}): no se pudo guardar la línea.")
