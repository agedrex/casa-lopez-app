"""Annul and correct racing on the same fixed cost (skipped without TEST_DATABASE_URL).

Uses two real sessions that commit, so it cleans up its own rows (the month 2099-01 is not in the seeds).
"""

import threading
import time
from decimal import Decimal as D

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.models import GastoPeriodo

PERIODO = "2099-01"


@pytest.fixture
def engine(local_postgres):
    yield local_postgres
    with Session(local_postgres) as limpieza:
        limpieza.execute(delete(GastoPeriodo).where(GastoPeriodo.periodo == PERIODO, GastoPeriodo.reemplaza_a_id.is_not(None)))
        limpieza.execute(delete(GastoPeriodo).where(GastoPeriodo.periodo == PERIODO))
        limpieza.commit()


def test_an_annul_waiting_on_a_correction_gets_a_conflict_and_never_flags_a_replaced_row(engine):
    with Session(engine) as preparar:
        servicios.crear_gasto(preparar, periodo=PERIODO, concepto="Seguro", fabrica_o_tienda="TIENDA", categoria="OTROS",
                              persona=None, monto_ars_del_mes=D("10"), ficticio=False, nota_fuente=None)
        codigo = preparar.scalar(select(GastoPeriodo.codigo).where(GastoPeriodo.periodo == PERIODO))

    corrector, anulador = Session(engine), Session(engine)
    resultado: dict = {}
    try:
        # The corrector takes the row lock first and keeps its transaction open.
        viejo = servicios._gasto_para_cambiar(corrector, codigo)

        def anular():
            try:
                servicios.anular_gasto(anulador, codigo)
                resultado["anular"] = "ok"
            except Exception as problema:  # the type is what the test asserts
                resultado["anular"] = problema

        hilo = threading.Thread(target=anular)
        hilo.start()
        time.sleep(0.5)
        assert hilo.is_alive(), "the annul must wait for the row lock instead of racing"
        corrector.add(GastoPeriodo(
            codigo="GF-9998", periodo=PERIODO, concepto=viejo.concepto, fabrica_o_tienda=viejo.fabrica_o_tienda,
            categoria=viejo.categoria, monto_ars_del_mes=D("20"), ficticio=False, nota_fuente=f"Corrige {codigo}",
            reemplaza_a_id=viejo.id))
        corrector.commit()
        hilo.join(timeout=10)
        assert not hilo.is_alive()
        assert isinstance(resultado["anular"], servicios.Conflicto), resultado
    finally:
        corrector.close()
        anulador.close()

    with Session(engine) as lectura:
        original = lectura.scalar(select(GastoPeriodo).where(GastoPeriodo.codigo == codigo))
        assert original.anulado is False  # a replaced row is never flagged
