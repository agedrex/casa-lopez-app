"""Read-only database diagnostics and non-sensitive stage catalog."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models import Etapa


router = APIRouter()


@router.get("/db/estado")
def database_state(session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        revision, count = session.execute(text(
            "SELECT (SELECT version_num FROM costos.alembic_version), "
            "(SELECT count(*) FROM information_schema.tables WHERE table_schema = 'costos' "
            "AND table_type = 'BASE TABLE' AND table_name <> 'alembic_version')"
        )).one()
        return {"ok": True, "alembic_revision": revision, "tablas_costos": count}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable.") from None


@router.get("/catalogo/etapas")
def stage_catalog(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    try:
        # The free-text columns (que_es_y_de_donde_viene, nota) name people and stay out of this unauthenticated route.
        statement = select(Etapa.codigo, Etapa.orden, Etapa.tipo, Etapa.va_siempre, Etapa.tratamiento).order_by(Etapa.orden)
        return [dict(row) for row in session.execute(statement).mappings().all()]
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable.") from None
