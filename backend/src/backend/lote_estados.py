"""The taller moves a lot forward, one state at a time (S11 of lanzamiento-listo).

SUPUESTO: validar. The cycle is PLANIFICADA, EN_CORTE, CORTADA, EN_CONFECCION, LISTA, CERRADA (`LOT_STATES`). The taller
only takes the next one and stops at LISTA: closing a lot needs the delivery date and freezes the final quote, so it stays
with the admin (`servicios.registrar_estado`, which keeps that rule). The date is today in Buenos Aires.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend import servicios
from backend.models import LOT_STATES

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def hoy_de_buenos_aires() -> date:
    return datetime.now(ZONA).date()


def siguiente_estado(actual: str) -> str | None:
    """The state after `actual` in the cycle; None after the last one."""
    posicion = LOT_STATES.index(actual)
    return LOT_STATES[posicion + 1] if posicion + 1 < len(LOT_STATES) else None


def avanzar_estado(session: Session, codigo: str, *, usuario_id: str) -> dict:
    """Move the lot to its next state, dated today, recording who did it. Never closes: that is the admin's."""
    orden = servicios._orden_por_codigo(session, codigo, bloquear=True)
    if orden.estado == "CERRADA":
        raise servicios.Conflicto(f"El lote {codigo} ya está cerrado: no se puede cambiar su estado.")
    siguiente = siguiente_estado(orden.estado)
    if siguiente is None or siguiente == "CERRADA":
        raise servicios.Conflicto(
            f"El lote {codigo} ya está listo. Cerrarlo (con la fecha de entrega) lo hace el administrador.")
    return servicios.registrar_estado(
        session, codigo, estado=siguiente, fecha=hoy_de_buenos_aires(), quien=None, fecha_de_entrega=None,
        usuario_id=usuario_id)
