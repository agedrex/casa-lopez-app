"""Materials grid: price changes and new materials saved together, all or nothing.

A price is never edited: a change on a saved material is a new dated row in `precio_material`, written by
`servicios.crear_precio` (the same service as the price form and the supplier page). The grid works with the price for
ALL colors (color NULL); prices by color keep their own history and are never touched here.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import ARS_USD, UNITS, Etapa, Material, PrecioMaterial
from backend.servicios import (
    MAX_FILAS_POR_LOTE, Conflicto, DatosInvalidos, NoEncontrado, _insertar, _nombre_repetido, _siguiente_numero,
    _texto_o_nada, crear_precio,
)

# SUPUESTO: validar. The origin noted on every price loaded from the grid.
NOTA_DE_LA_GRILLA = "Cargado desde la grilla de Materiales."


def _precio_vigente(session: Session, material_id: int, hoy: date) -> PrecioMaterial | None:
    """The price for all colors in force on `hoy` (the newest one not after it), or None."""
    return session.scalars(
        select(PrecioMaterial).where(
            PrecioMaterial.material_id == material_id, PrecioMaterial.color_id.is_(None), PrecioMaterial.vigente_desde <= hoy)
        .order_by(PrecioMaterial.vigente_desde.desc(), PrecioMaterial.id.desc()).limit(1)).first()


def _cargar_precio(
    session: Session, material: Material, *, precio: Decimal | None, moneda: str | None, proveedor: str | None,
    iva_incluido: bool, hoy: date,
) -> dict:
    try:
        return crear_precio(
            session, material=material.codigo, color=None, proveedor=proveedor, precio=precio, moneda=moneda,
            unidad_del_precio=material.unidad_de_consumo, iva_incluido=iva_incluido, vigente_desde=hoy,
            nota_fuente=NOTA_DE_LA_GRILLA, commit=False)
    except Conflicto:
        raise Conflicto(
            f"{material.codigo}: ya tiene un precio de hoy ({hoy:%d/%m/%Y}). Un precio no se edita: "
            "cargue el nuevo con otra fecha desde la página del proveedor.") from None


def _cambiar_precio(session: Session, cambio: dict, hoy: date) -> dict | None:
    codigo = cambio["codigo"]
    material = session.scalar(select(Material).where(Material.codigo == codigo))
    if material is None:
        raise NoEncontrado(f"No existe el material {codigo}.")
    if not material.cotizable:
        raise DatosInvalidos(f"{codigo}: bloqueado, falta definir la unidad de este material.")
    previo = _precio_vigente(session, material.id, hoy)
    precio = cambio.get("precio", previo.precio if previo else None)
    moneda = cambio.get("moneda") or (previo.moneda if previo else None)
    proveedor = _texto_o_nada(cambio["proveedor"]) if "proveedor" in cambio else (previo.proveedor if previo else None)
    if precio is None:
        raise DatosInvalidos(f"{codigo}: falta el precio.")
    if moneda is None:
        raise DatosInvalidos(f"{codigo}: falta la moneda del precio.")
    if previo and (previo.precio, previo.moneda, previo.proveedor) == (precio, moneda, proveedor):
        return None  # nothing changed: no new row in the history
    return _cargar_precio(
        session, material, precio=precio, moneda=moneda, proveedor=proveedor,
        iva_incluido=previo.iva_incluido if previo else False, hoy=hoy)


def _nuevo_material(session: Session, nuevo: dict, donde: str, hoy: date) -> tuple[Material, dict | None]:
    nombre = (nuevo.get("nombre") or "").strip()
    if not nombre:
        raise DatosInvalidos(f"{donde}: falta el nombre del material.")
    etapa = session.scalar(select(Etapa).where(Etapa.codigo == nuevo.get("etapa")))
    if etapa is None or etapa.tipo != "MATERIAL":
        raise DatosInvalidos(f"{donde}: elija una etapa de materiales (cuero, forro, flex, goma EVA, herrajes o hilo y cemento).")
    unidad = nuevo.get("unidad_de_consumo")
    if unidad not in UNITS:
        raise DatosInvalidos(f"{donde}: elija la unidad de consumo.")
    precio, moneda = nuevo.get("precio"), nuevo.get("moneda")
    if precio is not None and moneda not in ARS_USD:
        raise DatosInvalidos(f"{donde}: elija la moneda del precio.")
    if _nombre_repetido(session, Material.nombre, nombre):
        raise Conflicto(f"Ya hay un material con el nombre {nombre}.")
    # SUPUESTO: validar. `MAT-nnnn` is ours; the seeded materials keep their sheet codes (MAT-CU01...).
    fila = Material(
        codigo=f"MAT-{_siguiente_numero(session, Material.codigo, 'MAT'):04d}", nombre=nombre, etapa_id=etapa.id,
        unidad_de_consumo=unidad)
    _insertar(session, fila, "Ya hay un material con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    if precio is None:
        return fila, None
    return fila, _cargar_precio(
        session, fila, precio=precio, moneda=moneda, proveedor=_texto_o_nada(nuevo.get("proveedor")), iva_incluido=False,
        hoy=hoy)


def guardar_en_lote(
    session: Session, cambios: list[dict], nuevos: list[dict], *, hoy: date | None = None,
) -> dict:
    """Grid save, ONE transaction (all or nothing).

    `cambios`: {codigo, precio?, moneda?, proveedor?}; what is not sent stays as in the price in force today, and a change
    that leaves price, currency and supplier as they are adds nothing. `nuevos`: {nombre, etapa, unidad_de_consumo, precio?,
    moneda?, proveedor?}; a price makes the first row of its history. Returns the new prices (with the API's variation
    against the previous one) and the codes of the new materials.
    """
    if not cambios and not nuevos:
        raise DatosInvalidos("No hay cambios para guardar.")
    if len(cambios) + len(nuevos) > MAX_FILAS_POR_LOTE:
        raise DatosInvalidos(f"Son demasiadas filas de una vez (máximo {MAX_FILAS_POR_LOTE}).")
    codigos = [c["codigo"] for c in cambios]
    if len(set(codigos)) != len(codigos):
        raise DatosInvalidos("Hay un material repetido en los cambios.")
    hoy = hoy or date.today()
    precios, creados = [], []
    try:
        for cambio in cambios:
            if (cargado := _cambiar_precio(session, cambio, hoy)) is not None:
                precios.append(cargado)
        for indice, nuevo in enumerate(nuevos, start=1):
            fila, cargado = _nuevo_material(session, nuevo, f"Material nuevo {indice}", hoy)
            creados.append(fila.codigo)
            if cargado is not None:
                precios.append(cargado)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"precios": precios, "materiales_nuevos": creados}
