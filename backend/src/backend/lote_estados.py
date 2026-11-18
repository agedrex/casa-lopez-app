"""The taller moves a lot forward, one state at a time (S11 of lanzamiento-listo).

SUPUESTO: validar. The cycle is PLANIFICADA, EN_CORTE, CORTADA, EN_CONFECCION, LISTA, CERRADA (`LOT_STATES`). The taller
only takes the next one and stops at LISTA: closing a lot needs the delivery date and freezes the final quote, so it stays
with the admin (`servicios.registrar_estado`, which keeps that rule). The date is today in Buenos Aires.

SUPUESTO: validar con Robert (QA 2026-11-17). The taller cannot mark a lot CORTADA or LISTA while a line that uses leather has
no leather cut for it: the rule is the most conservative one, "every line with units, not removed, whose product has a leather
needs at least one CORTE movement" (the Corte screen is what writes it, `cueros.cortar`). It does not compare the m² cut with
the model's consumption, because nobody confirmed that a cut must reach it. The admin's own route does not check it.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import LOT_STATES, MovimientoCuero, OrdenEstado, OrdenItem, Producto, renglon_quitado

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
# The states the taller can only reach once the leather of every line was cut.
ESTADOS_CON_CUERO_CORTADO = ("CORTADA", "LISTA")
# "Deshacer" only reaches a change made this recently, so it cannot rewrite old history.
VENTANA_DESHACER = timedelta(minutes=10)
# States from which going back would mean reverting a leather cut (it is never reverted: the admin corrects it).
ESTADOS_QUE_PUEDEN_TENER_CORTE = ("EN_CORTE", "CORTADA")


def hoy_de_buenos_aires() -> date:
    return datetime.now(ZONA).date()


def siguiente_estado(actual: str) -> str | None:
    """The state after `actual` in the cycle; None after the last one."""
    posicion = LOT_STATES.index(actual)
    return LOT_STATES[posicion + 1] if posicion + 1 < len(LOT_STATES) else None


def estado_anterior(actual: str) -> str | None:
    """The state before `actual` in the cycle; None before the first one."""
    posicion = LOT_STATES.index(actual)
    return LOT_STATES[posicion - 1] if posicion > 0 else None


def ahora() -> datetime:
    return datetime.now(timezone.utc)


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


def retroceder_estado(session: Session, codigo: str, *, usuario_id: str) -> dict:
    """"Deshacer": append a row that takes the lot back ONE state; nothing is deleted or edited.

    SUPUESTO: validar con Robert (T5 de ux-heuristicas). Only the user who made the last change can undo it, within
    `VENTANA_DESHACER`, once (an undo is not undone again by another undo), never from the first state nor from CERRADA, and
    never over a leather cut: the CORTE movements are not reverted, the admin corrects them."""
    orden = servicios._orden_por_codigo(session, codigo, bloquear=True)
    if orden.estado == "CERRADA":
        raise servicios.Conflicto(f"El lote {codigo} ya está cerrado: no se puede cambiar su estado.")
    anterior = estado_anterior(orden.estado)
    if anterior is None:
        raise servicios.Conflicto(
            f"El lote {codigo} está en {servicios.ETIQUETA_ESTADO_LOTE[orden.estado]}: no hay un estado anterior al que volver.")
    ultimos = session.scalars(select(OrdenEstado).where(OrdenEstado.orden_fabricacion_id == orden.id)
                              .order_by(OrdenEstado.id.desc()).limit(2)).all()
    ultimo = ultimos[0]
    if ultimo.cambiado_por is None or ultimo.cambiado_por != usuario_id:
        raise servicios.Conflicto("Solo podés deshacer un cambio que hiciste vos: pedile a un administrador que lo corrija.")
    if ahora() - ultimo.created_at > VENTANA_DESHACER:
        raise servicios.Conflicto("Pasaron más de 10 minutos desde el último cambio: pedile a un administrador que lo corrija.")
    if len(ultimos) > 1 and LOT_STATES.index(ultimos[1].estado) > LOT_STATES.index(ultimo.estado):
        raise servicios.Conflicto("El último cambio ya se deshizo: no se puede volver más atrás.")
    if orden.estado in ESTADOS_QUE_PUEDEN_TENER_CORTE and session.scalar(
            select(exists().where(MovimientoCuero.orden_item_id == OrdenItem.id, MovimientoCuero.tipo == "CORTE",
                                  OrdenItem.orden_fabricacion_id == orden.id))):
        raise servicios.Conflicto("Ya se cortó cuero de este lote: pedile a un administrador que lo corrija.")
    servicios._insertar(
        session, OrdenEstado(orden_fabricacion_id=orden.id, estado=anterior, fecha=hoy_de_buenos_aires(), quien_id=None,
                             cambiado_por=usuario_id),
        "No se pudo registrar el estado del lote; intentá de nuevo.")
    orden.estado = anterior
    session.commit()
    return servicios.detalle_orden(session, codigo)
