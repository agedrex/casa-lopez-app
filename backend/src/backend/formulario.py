"""Consumption form of a new article ("formulario de consumos y herrajes"): the digital version of the paper sheet.

One form per article. The admin creates it with the preloaded rows (empty quantities), sends it to the workshop, the
workshop fills it in and completes it, and the admin validates it or sends it back with a review comment. This module
does NOT cost, calculate or convert anything (no USD, no totals): quantities are exactly what a person typed, and
nothing here touches `modelo`, `receta_linea` or the cost engine. Forms are never deleted.

State machine (`ACCIONES`):
    enviar     admin    BORRADOR | ENVIADO -> ENVIADO       (sets enviado_en; sending again re-sends it)
    completar  taller / admin    ENVIADO -> COMPLETADO      (sets completado_por / completado_en)
    devolver   admin    COMPLETADO -> ENVIADO               (needs a comment, stored in comentario_revision)
    validar    admin    COMPLETADO -> VALIDADO              (sets validado_por / validado_en)
    VALIDADO is immutable: any change is a 409 and the way to change it is `duplicar`.
    Validating also saves the supplies of the sheet (HERRAJE rows and a few CONSUMO rows with a quantity) as `modelo_insumo`
    of its model when a costable material has the same name, and answers the names that matched none in `sin_material`.

Who edits what (`comprobar_edicion`): the admin edits articulo, nota and the rows while BORRADOR / ENVIADO / COMPLETADO.
A `taller` user edits ONLY the rows (add, remove, rename, quantities, comments) and ONLY while ENVIADO. Who sees what
(`es_visible`): admin sees every form; `taller` sees only ENVIADO and COMPLETADO; `gerente` sees none (the module is closed to it).
SUPUESTO: validar. The `taller` role is not tied to one specific workshop, so any taller user sees every ENVIADO /
COMPLETADO form; `formulario_consumo.taller_id` is informative only.

HTTP (routes in api.py; errors are `{"detail": <Spanish message>}`: 403 not allowed, 404 missing or not visible,
409 invalid transition or immutable form, 422 invalid data):
    POST /formularios                       admin   {articulo, taller?, producto?, nota?} -> BORRADOR with the preloaded rows
    GET  /formularios?q=&estado=&producto=  admin, taller (taller: only ENVIADO / COMPLETADO); producto = PRD-NNNN
    GET  /formularios/{codigo}              same visibility; 404 otherwise
    PUT  /formularios/{codigo}              admin or taller; {articulo, nota?, lineas: [{seccion, nombre, cantidad?, comentario?}]}
                                            replaces articulo / nota and the FULL set of rows (list order = row order
                                            inside each section). A taller must send articulo / nota unchanged.
    POST /formularios/{codigo}/enviar       admin
    POST /formularios/{codigo}/completar    admin or taller
    POST /formularios/{codigo}/devolver     admin   {comentario}
    POST /formularios/{codigo}/validar      admin
    POST /formularios/{codigo}/duplicar     admin   {articulo} -> new BORRADOR copying the rows (names, quantities, comments)
"""

import unicodedata
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from backend.auth import ADMIN, TALLER
from backend.costeo import MATERIAL_STAGES
from backend.models import (
    FORM_SECTIONS, FORM_STATES, Etapa, FormularioConsumo, FormularioConsumoLinea, Material, Modelo, ModeloInsumo, Producto,
    Taller,
)
from backend.servicios import (
    Conflicto, DatosInvalidos, NoEncontrado, _insertar, _patron, _por_codigo, _siguiente_numero, _texto_o_nada,
)

BORRADOR, ENVIADO, COMPLETADO, VALIDADO = FORM_STATES
CONSUMO, HERRAJE = FORM_SECTIONS

# The ONLY place with the preloaded rows of the paper sheet: names and order of the CONSUMOS table and the HERRAJES table.
LINEAS_PRECARGADAS: dict[str, tuple[str, ...]] = {
    CONSUMO: (
        "CUERO", "FORRO / TELA", "FORRO / POTRO", "GOMA EVA", "FRISELINA", "CARTÓN FIBRA", "FLEX", "CARTULINA", "MOIRE",
        "HS. DE TRABAJO", "Y/O MANO DE OBRA TALLER", "DESPERDICIO 30%", "CORTE MANO DE OBRA", "EMPAQUE",
    ),
    HERRAJE: (
        "CIERRE N5", "CIERRE N3", "DESLIZADOR N5", "DESLIZADOR N3", "HEBILLA", "MOSQUETÓN", "MEDIA LUNA", "ARGOLLA 10MM",
        "IMÁN", "TORNIQUETE", "CADENA", "REMACHES", "SPAGUETTI", "TRENCILLA", "MANGUERA", "OJALILLO",
    ),
}

# action -> (states it can start from, state it leaves the form in, roles that may do it)
ACCIONES: dict[str, tuple[frozenset[str], str, frozenset[str]]] = {
    "enviar": (frozenset({BORRADOR, ENVIADO}), ENVIADO, frozenset({ADMIN})),
    "completar": (frozenset({ENVIADO}), COMPLETADO, frozenset({ADMIN, TALLER})),
    "devolver": (frozenset({COMPLETADO}), ENVIADO, frozenset({ADMIN})),
    "validar": (frozenset({COMPLETADO}), VALIDADO, frozenset({ADMIN})),
}
_QUE_SE_PUEDE = {
    "enviar": "Solo se puede enviar al taller un formulario en borrador o ya enviado",
    "completar": "Solo se puede completar un formulario enviado al taller",
    "devolver": "Solo se puede devolver a revisión un formulario completado",
    "validar": "Solo se puede validar un formulario completado",
}
MENSAJE_VALIDADO = "El formulario ya está validado y no se puede modificar: duplicalo para hacer cambios."
ESTADOS_VISIBLES_PARA_TALLER = frozenset({ENVIADO, COMPLETADO})
MAX_LINEAS = 200  # per form; far above the 30 rows of the sheet, only a guard against absurd bodies


class SinPermiso(Exception):
    """The caller's role cannot do this on this form (HTTP 403)."""


# --- Pure rules (no database, no clock) -------------------------------------------------------------------------------

def lineas_precargadas() -> list[dict]:
    """The rows of a new form: the two tables of the sheet in order, quantities and comments empty."""
    return [
        {"seccion": seccion, "orden": orden, "nombre": nombre, "cantidad": None, "comentario": None}
        for seccion, nombres in LINEAS_PRECARGADAS.items() for orden, nombre in enumerate(nombres, start=1)
    ]


def es_visible(estado: str, roles: frozenset[str]) -> bool:
    """Admin sees every form; taller only the ones sent to it (ENVIADO) or completed (COMPLETADO); any other role none."""
    if ADMIN in roles:
        return True
    return TALLER in roles and estado in ESTADOS_VISIBLES_PARA_TALLER


def comprobar_edicion(estado: str, roles: frozenset[str]) -> bool:
    """Raise unless `roles` may edit a form in `estado`; return True when only the rows may change (taller)."""
    if estado == VALIDADO:
        raise Conflicto(MENSAJE_VALIDADO)
    if ADMIN in roles:
        return False
    if TALLER in roles:
        if estado == BORRADOR:
            raise Conflicto("El formulario todavía no fue enviado al taller.")
        if estado == COMPLETADO:
            raise Conflicto("El formulario ya fue completado: esperá a que lo revise el administrador.")
        return True
    raise SinPermiso("No tenés permiso para modificar este formulario.")


def siguiente_estado(accion: str, estado: str, roles: frozenset[str]) -> str:
    """The state `accion` leaves a form in `estado`, or an error: SinPermiso (role) / Conflicto (invalid transition)."""
    desde, hasta, quienes = ACCIONES[accion]
    if not roles & quienes:
        raise SinPermiso("No tenés permiso para esta acción.")
    if estado == VALIDADO:
        raise Conflicto(MENSAJE_VALIDADO)
    if estado not in desde:
        raise Conflicto(f"{_QUE_SE_PUEDE[accion]}; este formulario está {estado.lower()}.")
    return hasta


def armar_lineas(lineas: list[dict]) -> list[dict]:
    """Validate the full set of rows and number them: `orden` is the position inside each section, starting at 1.

    A name is required (trimmed); the quantity is None or a decimal >= 0; an empty comment is stored as None.
    """
    if len(lineas) > MAX_LINEAS:
        raise DatosInvalidos(f"El formulario admite hasta {MAX_LINEAS} filas.")
    cuenta = {seccion: 0 for seccion in FORM_SECTIONS}
    armadas = []
    for linea in lineas:
        seccion = linea.get("seccion")
        if seccion not in cuenta:
            raise DatosInvalidos("La sección de cada fila tiene que ser CONSUMO o HERRAJE.")
        nombre = (linea.get("nombre") or "").strip()
        if not nombre:
            raise DatosInvalidos("Cada fila tiene que tener un nombre.")
        cantidad = linea.get("cantidad")
        if cantidad is not None and (not isinstance(cantidad, Decimal) or not cantidad.is_finite() or cantidad < 0):
            raise DatosInvalidos(f"La cantidad de {nombre} tiene que ser un número mayor o igual a cero.")
        cuenta[seccion] += 1
        armadas.append({
            "seccion": seccion, "orden": cuenta[seccion], "nombre": nombre, "cantidad": cantidad,
            "comentario": _texto_o_nada(linea.get("comentario")),
        })
    return sorted(armadas, key=lambda l: (FORM_SECTIONS.index(l["seccion"]), l["orden"]))


def _articulo(valor: str | None) -> str:
    articulo = (valor or "").strip()
    if not articulo:
        raise DatosInvalidos("Falta el artículo (nombre o código).")
    return articulo


# --- Reads ------------------------------------------------------------------------------------------------------------

def _resumen(fila: FormularioConsumo, producto: str | None, taller: str | None, modelo: str | None = None) -> dict:
    return {
        "codigo": fila.codigo, "articulo": fila.articulo, "estado": fila.estado, "producto": producto, "taller": taller, "modelo": modelo,
        "creado_por": fila.creado_por, "created_at": fila.created_at, "enviado_en": fila.enviado_en,
        "completado_en": fila.completado_en, "validado_en": fila.validado_en,
    }


def _detalle(
    session: Session, fila: FormularioConsumo, producto: str | None, taller: str | None, modelo: str | None = None,
) -> dict:
    lineas = session.scalars(
        select(FormularioConsumoLinea).where(FormularioConsumoLinea.formulario_id == fila.id)
        .order_by(FormularioConsumoLinea.seccion, FormularioConsumoLinea.orden)  # CONSUMO sorts before HERRAJE
    ).all()
    return {
        **_resumen(fila, producto, taller, modelo),
        "nota": fila.nota, "comentario_revision": fila.comentario_revision,
        "completado_por": fila.completado_por, "validado_por": fila.validado_por,
        "lineas": [{"seccion": l.seccion, "orden": l.orden, "nombre": l.nombre, "cantidad": l.cantidad,
                    "comentario": l.comentario} for l in lineas],
    }


def _consulta_base():
    return (
        select(FormularioConsumo, Producto.codigo, Taller.codigo, Modelo.codigo)
        .outerjoin(Producto, Producto.id == FormularioConsumo.producto_id)
        .outerjoin(Modelo, Modelo.id == FormularioConsumo.modelo_id)
        .outerjoin(Taller, Taller.id == FormularioConsumo.taller_id)
    )


def _cargar(session: Session, codigo: str, roles: frozenset[str], *, bloquear: bool = False):
    """The form and its product / workshop codes; 404 when it does not exist OR the caller may not see it."""
    consulta = _consulta_base().where(FormularioConsumo.codigo == codigo)
    if bloquear:
        consulta = consulta.with_for_update(of=FormularioConsumo)  # two saves / transitions of one form do not interleave
    encontrado = session.execute(consulta).one_or_none()
    if encontrado is None or not es_visible(encontrado[0].estado, roles):
        raise NoEncontrado(f"No existe el formulario {codigo}.")
    return encontrado


def listar_formularios(
    session: Session, *, q: str | None, estado: str | None, roles: frozenset[str], producto: str | None = None,
) -> list[dict]:
    """Newest first. Every word of `q` must appear in the code, the article, the product code or the workshop name.

    `producto` (a PRD-NNNN code) keeps only the forms linked to that product: the product sheet uses it to show its validated form.
    """
    if estado is not None and estado not in FORM_STATES:
        raise DatosInvalidos(f"El estado tiene que ser uno de: {', '.join(FORM_STATES)}.")
    consulta = _consulta_base().order_by(FormularioConsumo.id.desc())
    if ADMIN not in roles:
        consulta = consulta.where(FormularioConsumo.estado.in_(sorted(ESTADOS_VISIBLES_PARA_TALLER)))
    if estado:
        consulta = consulta.where(FormularioConsumo.estado == estado)
    if producto:
        consulta = consulta.where(Producto.codigo == producto)
    for palabra in (q or "").split():
        patron = _patron(palabra)
        consulta = consulta.where(or_(*(columna.ilike(patron, escape="\\") for columna in (
            FormularioConsumo.codigo, FormularioConsumo.articulo, Producto.codigo, Taller.nombre))))
    return [_resumen(*fila) for fila in session.execute(consulta).all()]


def obtener_formulario(session: Session, codigo: str, roles: frozenset[str]) -> dict:
    return _detalle(session, *_cargar(session, codigo, roles))


# --- Writes -----------------------------------------------------------------------------------------------------------

def _nuevo(session: Session, *, articulo: str, producto_id, taller_id, nota: str | None, quien: str, lineas: list[dict]) -> FormularioConsumo:
    fila = FormularioConsumo(
        codigo=f"FCO-{_siguiente_numero(session, FormularioConsumo.codigo, 'FCO'):04d}", articulo=articulo,
        producto_id=producto_id, taller_id=taller_id, estado=BORRADOR, nota=_texto_o_nada(nota), creado_por=quien)
    _insertar(session, fila, "Ya existe un formulario con ese código: probá de nuevo.")
    session.add_all(FormularioConsumoLinea(formulario_id=fila.id, **linea) for linea in lineas)
    session.flush()
    return fila


def crear_formulario(
    session: Session, *, articulo: str, taller: str | None, producto: str | None, nota: str | None, quien: str,
) -> dict:
    """A BORRADOR with the preloaded rows (empty quantities and comments)."""
    articulo = _articulo(articulo)
    fila_producto = _por_codigo(session, Producto, producto, "el producto")
    fila_taller = _por_codigo(session, Taller, taller, "el taller")
    fila = _nuevo(
        session, articulo=articulo, producto_id=fila_producto.id if fila_producto else None,
        taller_id=fila_taller.id if fila_taller else None,
        nota=nota, quien=quien, lineas=lineas_precargadas())
    session.commit()
    return _detalle(session, fila, producto, taller)


# Rows of the form whose measure goes to the model when the admin validates (m2 per unit). FORRO is not copied: the model also
# needs the lining material, a choice a person makes. HERRAJES are quantities, not the USD amount the model keeps.
MEDIDAS_AL_VALIDAR = {"CUERO": "cuero_m2_por_unidad", "FLEX": "flex_m2_por_unidad", "GOMA EVA": "goma_eva_m2_por_unidad"}


def normalizar_nombre(nombre: str | None) -> str:
    """One house style for names: single spaces and CAPITALS."""
    limpio = " ".join((nombre or "").split()).upper()
    if not limpio:
        raise DatosInvalidos("Falta el nombre del producto.")
    return limpio


def alta_rapida(session: Session, *, nombre: str, quien: str) -> dict:
    """New model from its name alone, with its consumption form already sent to the workshop, in one transaction.

    The model is what gets designed and measured; the product (model + leather + colour) is created after validation.
    """
    nombre = normalizar_nombre(nombre)
    if any(existente.casefold() == nombre.casefold() for existente in session.scalars(select(Modelo.nombre_del_modelo))):
        raise Conflicto(f"Ya hay un modelo llamado {nombre}: agregá algo que lo distinga.")
    # SUPUESTO: validar. Category and size stay empty until someone completes them.
    modelo = Modelo(
        codigo=f"MOD-{_siguiente_numero(session, Modelo.codigo, 'MOD'):04d}", nombre_del_modelo=nombre, validado=False)
    _insertar(session, modelo, "Ya hay un modelo con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    fila = _nuevo(
        session, articulo=nombre, producto_id=None, taller_id=None, nota=None, quien=quien, lineas=lineas_precargadas())
    fila.modelo_id, fila.estado, fila.enviado_en = modelo.id, ENVIADO, datetime.now(timezone.utc)
    session.commit()
    return {"modelo": modelo.codigo, "formulario": fila.codigo, "nombre": nombre}


# Rows of the CONSUMO table that are supplies bought by the unit (the rest of the table is leather, lining, hours...).
# Every row of the HERRAJE table is a supply. SUPUESTO: validar con Gerardo (the list and the name match are our convention).
INSUMOS_DE_CONSUMO = ("FRISELINA", "CARTÓN FIBRA", "CARTULINA", "MOIRE")


def normalizar_para_comparar(nombre: str | None) -> str:
    """Name for matching: no accents, no case, single spaces (CARTÓN  Fibra == carton fibra)."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", nombre or "") if not unicodedata.combining(c))
    return " ".join(sin_tildes.casefold().split())


def separar_insumos(
    lineas: list[tuple[str, str, Decimal | None]], materiales: list[tuple[int, str, str | None]],
) -> tuple[dict[int, Decimal], list[str]]:
    """Split the rows of a form into supplies per material id and the names that matched no material.

    `lineas` are (seccion, nombre, cantidad); only HERRAJE rows and the CONSUMO rows of `INSUMOS_DE_CONSUMO` with a quantity
    above 0 count. `materiales` are (id, nombre, nombre_corto) of the materials a supply may point to. A name that fits two
    different materials is not guessed: it goes to the unmatched list. Rows of the same material add up.
    """
    candidatos: dict[str, set[int]] = {}
    for material_id, nombre, nombre_corto in materiales:
        for texto in (nombre, nombre_corto):
            if texto:
                candidatos.setdefault(normalizar_para_comparar(texto), set()).add(material_id)
    de_consumo = {normalizar_para_comparar(n) for n in INSUMOS_DE_CONSUMO}
    cantidades: dict[int, Decimal] = {}
    sin_material: list[str] = []
    vistos: set[str] = set()
    for seccion, nombre, cantidad in lineas:
        clave = normalizar_para_comparar(nombre)
        if cantidad is None or cantidad <= 0 or not clave or (seccion == CONSUMO and clave not in de_consumo):
            continue
        ids = candidatos.get(clave, set())
        if len(ids) == 1:
            (material_id,) = ids
            cantidades[material_id] = cantidades.get(material_id, Decimal(0)) + cantidad
        elif clave not in vistos:
            vistos.add(clave)
            sin_material.append(" ".join(nombre.split()))
    return cantidades, sin_material


def _guardar_insumos(session: Session, modelo: Modelo, fila: FormularioConsumo) -> list[str]:
    """Save the supplies of the form as `modelo_insumo` rows of the model (one per material, updated if it already exists,
    removed when the sheet no longer lists it) and return the names with a quantity that matched no costable material (those are not saved)."""
    materiales = session.execute(
        select(Material.id, Material.nombre, Material.nombre_corto)
        .join(Etapa, Etapa.id == Material.etapa_id)
        .where(Material.cotizable.is_(True), Etapa.codigo.in_(MATERIAL_STAGES)).order_by(Material.id)
    ).all()
    lineas = session.execute(
        select(FormularioConsumoLinea.seccion, FormularioConsumoLinea.nombre, FormularioConsumoLinea.cantidad)
        .where(FormularioConsumoLinea.formulario_id == fila.id)
        .order_by(FormularioConsumoLinea.seccion, FormularioConsumoLinea.orden)
    ).all()
    cantidades, sin_material = separar_insumos([tuple(l) for l in lineas], [tuple(m) for m in materiales])
    existentes = {i.material_id: i for i in session.scalars(select(ModeloInsumo).where(ModeloInsumo.modelo_id == modelo.id))}
    for material_id, cantidad in cantidades.items():
        if material_id in existentes:
            existentes[material_id].cantidad_por_unidad = cantidad
        else:
            _insertar(session, ModeloInsumo(
                codigo=f"MIN-{_siguiente_numero(session, ModeloInsumo.codigo, 'MIN'):04d}", modelo_id=modelo.id,
                material_id=material_id, cantidad_por_unidad=cantidad,
            ), "Ya hay un insumo de ese material en el modelo: probá de nuevo.")
    for material_id, insumo in existentes.items():  # the validated sheet is the truth: supplies it no longer lists go
        if material_id not in cantidades:
            session.delete(insumo)
    return sin_material


def _aplicar_medidas(session: Session, fila: FormularioConsumo) -> list[str] | None:
    """On validation, copy the measured m2 to the sheet's model and save its supplies, unless that model was already validated.

    Returns the rows with a quantity that matched no material, or None when the model was not touched.
    """
    modelo_id = fila.modelo_id
    if modelo_id is None and fila.producto_id is not None:  # forms made before 0017 only know their product
        modelo_id = session.scalar(select(Producto.modelo_id).where(Producto.id == fila.producto_id))
    modelo = session.get(Modelo, modelo_id) if modelo_id is not None else None
    if modelo is None or modelo.validado:
        return None
    for linea in session.scalars(select(FormularioConsumoLinea).where(
            FormularioConsumoLinea.formulario_id == fila.id, FormularioConsumoLinea.seccion == CONSUMO)):
        campo = MEDIDAS_AL_VALIDAR.get(linea.nombre.strip().upper())
        if campo and linea.cantidad is not None:
            setattr(modelo, campo, linea.cantidad)
    modelo.origen_de_los_consumos, modelo.validado = "MEDIDO", True
    return _guardar_insumos(session, modelo, fila)


def guardar_formulario(
    session: Session, codigo: str, *, articulo: str, nota: str | None, lineas: list[dict], roles: frozenset[str],
) -> dict:
    """Replace articulo / nota and the FULL set of rows. A taller user may change only the rows (it sends articulo / nota as they are)."""
    fila, producto, taller, modelo = _cargar(session, codigo, roles, bloquear=True)
    solo_lineas = comprobar_edicion(fila.estado, roles)
    nuevas = armar_lineas(lineas)
    articulo = _articulo(articulo)
    if solo_lineas:
        if articulo != fila.articulo or _texto_o_nada(nota) != fila.nota:
            raise SinPermiso("El taller solo puede completar las filas del formulario: el artículo y la nota los cambia el administrador.")
    else:
        fila.articulo, fila.nota = articulo, _texto_o_nada(nota)
    # Explicit DELETE first: the unit of work would insert the new rows before removing the old ones and trip the unique key.
    session.execute(delete(FormularioConsumoLinea).where(FormularioConsumoLinea.formulario_id == fila.id))
    session.add_all(FormularioConsumoLinea(formulario_id=fila.id, **linea) for linea in nuevas)
    session.commit()  # get_session rolls back whatever is not committed
    return _detalle(session, fila, producto, taller, modelo)


def cambiar_estado(
    session: Session, codigo: str, accion: str, *, roles: frozenset[str], quien: str, comentario: str | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Apply one action of `ACCIONES` and stamp who / when. `devolver` needs a non-empty comment."""
    ahora = ahora or datetime.now(timezone.utc)
    fila, producto, taller, modelo = _cargar(session, codigo, roles, bloquear=True)
    nuevo = siguiente_estado(accion, fila.estado, roles)
    sin_material = None
    if accion == "devolver":
        comentario = _texto_o_nada(comentario)
        if comentario is None:
            raise DatosInvalidos("Escribí el comentario de revisión para devolver el formulario al taller.")
        fila.comentario_revision = comentario
    elif accion == "enviar":
        fila.enviado_en = ahora
    elif accion == "completar":
        fila.completado_por, fila.completado_en = quien, ahora
    elif accion == "validar":
        fila.validado_por, fila.validado_en = quien, ahora
        sin_material = _aplicar_medidas(session, fila)
    fila.estado = nuevo
    session.commit()  # get_session rolls back whatever is not committed
    detalle = _detalle(session, fila, producto, taller, modelo)
    if sin_material is not None:  # only the answer of `validar` carries it
        detalle["sin_material"] = sin_material
    return detalle


def duplicar_formulario(session: Session, codigo: str, *, articulo: str, quien: str, roles: frozenset[str]) -> dict:
    """A new BORRADOR for another article with a copy of the rows (names, quantities, comments) of a form in any state.

    The product, workshop and note are not copied: the new article is its own sheet.
    """
    if ADMIN not in roles:
        raise SinPermiso("No tenés permiso para esta acción.")
    articulo = _articulo(articulo)
    origen, _, _, _ = _cargar(session, codigo, roles)
    copiadas = [
        {"seccion": l.seccion, "orden": l.orden, "nombre": l.nombre, "cantidad": l.cantidad, "comentario": l.comentario}
        for l in session.scalars(select(FormularioConsumoLinea).where(FormularioConsumoLinea.formulario_id == origen.id))
    ]
    fila = _nuevo(session, articulo=articulo, producto_id=None, taller_id=None, nota=None, quien=quien, lineas=copiadas)
    session.commit()
    return _detalle(session, fila, None, None)
