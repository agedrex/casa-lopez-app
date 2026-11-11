"""Annul and correct racing on the same fixed cost (skipped without TEST_DATABASE_URL).

Uses two real sessions that commit, so it cleans up its own rows (the month 2099-01 is not in the seeds).
"""

import threading
import time
from decimal import Decimal as D

import pytest
from sqlalchemy import delete, func, select
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


def test_two_batches_touching_the_same_rows_in_opposite_order_do_not_deadlock(engine, monkeypatch):
    with Session(engine) as preparar:
        for concepto in ("Luz", "Gas"):
            servicios.crear_gasto(preparar, periodo=PERIODO, concepto=concepto, fabrica_o_tienda="TIENDA",
                                  categoria="OTROS", persona=None, monto_ars_del_mes=D("10"), ficticio=False,
                                  nota_fuente=None)
        r1, r2 = preparar.scalars(select(GastoPeriodo.codigo).where(GastoPeriodo.periodo == PERIODO).order_by(GastoPeriodo.id))

    original = servicios._gasto_para_cambiar

    def lento(session, codigo, periodo=None):
        fila = original(session, codigo, periodo)
        time.sleep(0.3)  # widens the window in which each batch holds one row and wants the other
        return fila

    monkeypatch.setattr(servicios, "_gasto_para_cambiar", lento)
    resultado: dict = {}

    def guardar(nombre, orden, monto):
        try:
            with Session(engine) as sesion:
                servicios.guardar_gastos_en_lote(sesion, PERIODO, [{"codigo": c, "monto": D(monto)} for c in orden], [])
            resultado[nombre] = "ok"
        except Exception as problema:
            resultado[nombre] = problema

    hilos = [threading.Thread(target=guardar, args=("A", [r1, r2], "111")),
             threading.Thread(target=guardar, args=("B", [r2, r1], "222"))]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=15)
    assert not any(hilo.is_alive() for hilo in hilos)
    # One batch wins; the other waits and then gets a clean conflict, never a database deadlock.
    assert sorted(type(v).__name__ if v != "ok" else "ok" for v in resultado.values()) == ["Conflicto", "ok"], resultado
    with Session(engine) as lectura:
        vigentes = servicios.costos_fijos(lectura, PERIODO)["gastos"]
        assert len(vigentes) == 2 and len({g["monto_ars_del_mes"] for g in vigentes}) == 1


def _dos_gastos(engine):
    with Session(engine) as sesion:
        for concepto in ("Luz", "Gas"):
            servicios.crear_gasto(sesion, periodo=PERIODO, concepto=concepto, fabrica_o_tienda="TIENDA",
                                  categoria="OTROS", persona=None, monto_ars_del_mes=D("10"), ficticio=False,
                                  nota_fuente=None)
        return list(sesion.scalars(select(GastoPeriodo.codigo).where(GastoPeriodo.periodo == PERIODO).order_by(GastoPeriodo.id)))


def _correr_juntos(engine, monkeypatch, *trabajos):
    """Runs the jobs in threads, each holding every row it touched for a moment; returns the sorted outcomes."""
    original = servicios._gasto_para_cambiar

    def lento(session, codigo, periodo=None):
        fila = original(session, codigo, periodo)
        time.sleep(0.3)
        return fila

    monkeypatch.setattr(servicios, "_gasto_para_cambiar", lento)
    resultado: dict = {}

    def correr(nombre, trabajo):
        try:
            with Session(engine) as sesion:
                trabajo(sesion)
            resultado[nombre] = "ok"
        except Exception as problema:
            resultado[nombre] = type(problema).__name__

    hilos = [threading.Thread(target=correr, args=trabajo) for trabajo in trabajos]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=15)
    assert not any(hilo.is_alive() for hilo in hilos)
    return sorted(resultado.values())


def test_crossed_batches_mixing_change_and_annul_do_not_deadlock(engine, monkeypatch):
    r1, r2 = _dos_gastos(engine)
    assert _correr_juntos(
        engine, monkeypatch,
        ("A", lambda s: servicios.guardar_gastos_en_lote(s, PERIODO, [{"codigo": r1, "monto": D("1")}], [], anulados=[r2])),
        ("B", lambda s: servicios.guardar_gastos_en_lote(s, PERIODO, [{"codigo": r2, "monto": D("2")}], [], anulados=[r1])),
    ) == ["Conflicto", "ok"]


def test_a_batch_and_a_single_correction_do_not_deadlock(engine, monkeypatch):
    r1, r2 = _dos_gastos(engine)
    assert _correr_juntos(
        engine, monkeypatch,
        ("A", lambda s: servicios.guardar_gastos_en_lote(
            s, PERIODO, [{"codigo": r1, "monto": D("1")}, {"codigo": r2, "monto": D("1")}], [])),
        ("B", lambda s: servicios.corregir_gasto(s, r2, D("2"))),
    ) == ["Conflicto", "ok"]


def test_a_batch_with_an_unknown_code_saves_nothing(engine):
    r1, _ = _dos_gastos(engine)
    with Session(engine) as sesion, pytest.raises(servicios.NoEncontrado):
        servicios.guardar_gastos_en_lote(
            sesion, PERIODO, [{"codigo": r1, "monto": D("50")}, {"codigo": "GF-9999", "monto": D("1")}],
            [{"concepto": "N", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"}])
    with Session(engine) as lectura:
        assert lectura.scalar(select(func.count()).select_from(GastoPeriodo).where(GastoPeriodo.periodo == PERIODO)) == 2
