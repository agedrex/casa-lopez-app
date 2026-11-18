"""The taller moves a lot forward, one state at a time (S11 of lanzamiento-listo).

SUPUESTO: validar. The cycle is PLANIFICADA, EN_CORTE, CORTADA, EN_CONFECCION, LISTA, CERRADA (`LOT_STATES`). The taller
only takes the next one and stops at LISTA: closing a lot needs the delivery date and freezes the final quote, so it stays
with the admin (`servicios.registrar_estado`, which keeps that rule). The date is today in Buenos Aires.

SUPUESTO: validar con Robert (QA 2026-11-17). The taller cannot mark a lot CORTADA or LISTA while a line that uses leather has
no leather cut for it: the rule is the most conservative one, "every line with units, not removed, whose product has a leather
needs at least one CORTE movement" (the Corte screen is what writes it, `cueros.cortar`). It does not compare the m² cut with
the model's consumption, because nobody confirmed that a cut must reach it. The admin's own route does not check it.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import LOT_STATES, MovimientoCuero, OrdenItem, Producto, renglon_quitado

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
# The states the taller can only reach once the leather of every line was cut.
ESTADOS_CON_CUERO_CORTADO = ("CORTADA", "LISTA")


def hoy_de_buenos_aires() -> date:
    return datetime.now(ZONA).date()


def siguiente_estado(actual: str) -> str | None:
    """The state after `actual` in the cycle; None after the last one."""
    posicion = LOT_STATES.index(actual)
    return LOT_STATES[posicion + 1] if posicion + 1 < len(LOT_STATES) else None


def renglones_sin_cuero_cortado(session: Session, lote_id: int) -> list[tuple[str, str]]:
    """(line, product) codes of the lot's live lines that use leather and have no cut recorded for them."""
    con_corte = exists().where(MovimientoCuero.orden_item_id == OrdenItem.id, MovimientoCuero.tipo == "CORTE")
    return [(item, producto) for item, producto in session.execute(
        select(OrdenItem.codigo, Producto.codigo).join(Producto, Producto.id == OrdenItem.producto_id)
        .where(OrdenItem.orden_fabricacion_id == lote_id, OrdenItem.cantidad > 0, ~renglon_quitado(),
               Producto.cuero_id.is_not(None), ~con_corte)
        .order_by(OrdenItem.id)).all()]


def avanzar_estado(session: Session, codigo: str, *, usuario_id: str) -> dict:
    """Move the lot to its next state, dated today, recording who did it. Never closes: that is the admin's."""
    orden = servicios._orden_por_codigo(session, codigo, bloquear=True)
    if orden.estado == "CERRADA":
        raise servicios.Conflicto(f"El lote {codigo} ya está cerrado: no se puede cambiar su estado.")
    siguiente = siguiente_estado(orden.estado)
    if siguiente is None or siguiente == "CERRADA":
        raise servicios.Conflicto(
            f"El lote {codigo} ya está listo. Cerrarlo (con la fecha de entrega) lo hace el administrador.")
    if siguiente in ESTADOS_CON_CUERO_CORTADO:
        faltan = renglones_sin_cuero_cortado(session, orden.id)
        if faltan:
            detalle = ", ".join(f"{producto} (renglón {item})" for item, producto in faltan)
            raise servicios.Conflicto(
                f"No se puede pasar el lote {codigo} a {servicios.ETIQUETA_ESTADO_LOTE[siguiente]}: falta registrar el cuero "
                f"cortado de {detalle}. Primero hay que cortar el cuero en la pantalla Corte.")
    return servicios.registrar_estado(
        session, codigo, estado=siguiente, fecha=hoy_de_buenos_aires(), quien=None, fecha_de_entrega=None,
        usuario_id=usuario_id)
