"""The example-data loader against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
The month is the real current one: the panel and the trend answer for "this month" as of today.
"""

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import (
    Color, GastoPeriodo, OrdenEstado, OrdenFabricacion, OrdenItem, PrecioMaterial, Producto, TipoCambio,
)

_spec = importlib.util.spec_from_file_location("cargar_ejemplo", Path(__file__).parents[1] / "scripts" / "cargar_ejemplo.py")
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)

HOY = date.today()
AHORA = servicios.mes_de(HOY)
TABLAS = (GastoPeriodo, TipoCambio, PrecioMaterial, Color, Producto, OrdenFabricacion, OrdenItem, OrdenEstado)


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-ejemplo", role="admin"))
    try:
        with TestClient(app) as client:
            client.session = session
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def conteos(session):
    return {tabla.__tablename__: session.scalar(select(func.count()).select_from(tabla)) for tabla in TABLAS}


def cargar(api, **opciones):
    return ce.cargar_ejemplo(api.session, AHORA, HOY, **opciones)


def test_a_second_run_creates_nothing(api):
    primera = cargar(api)
    despues_de_la_primera = conteos(api.session)
    assert primera.total_creado > 60
    segunda = cargar(api)
    assert segunda.total_creado == 0 and segunda.creados == {}
    assert conteos(api.session) == despues_de_la_primera


def test_dry_run_writes_nothing_and_reports_what_the_real_run_creates(api):
    antes = conteos(api.session)
    simulada = cargar(api, escribir=False)
    assert conteos(api.session) == antes
    real = cargar(api)
    assert simulada.creados == real.creados and simulada.total_creado == real.total_creado


def test_the_trend_shows_six_complete_enough_months(api):
    cargar(api)
    tendencia = api.get("/panel/tendencia", params={"hasta": AHORA}).json()
    meses = tendencia["meses"]
    assert len(meses) == 6 and meses[-1]["periodo"] == AHORA
    assert all("SIN_UNIDADES" not in m["incompleto"] for m in meses)
    assert all("PRODUCTOS_SIN_COSTO" not in m["incompleto"] for m in meses)
    assert any("FIJOS_FICTICIOS" in m["incompleto"] for m in meses)
    assert "FIJOS_PENDIENTES" in meses[-1]["incompleto"]
    assert all(float(m["unidades"]) > 0 and m["costo_variable_por_unidad"] is not None for m in meses)


def test_the_panel_has_units_a_variable_cost_and_the_price_blocks(api):
    cargar(api)
    panel = api.get("/panel/costos", params={"periodo": AHORA}).json()
    assert float(panel["actual"]["unidades"]) > 0 and float(panel["actual"]["unidades_sin_costo"]) == 0
    assert panel["actual"]["costo_variable_por_unidad"] is not None
    assert panel["precios_que_subieron"]
    assert panel["precios_viejos"]["cantidad"] >= 1
    assert panel["dolar"] is not None and not panel["dolar_viejo"]
    codigos = {a["codigo"] for a in panel["avisos"]}
    assert "PRODUCTOS_SIN_COSTO" not in codigos and "SIN_UNIDADES" not in codigos


def test_the_corrected_month_shows_the_new_amount_once(api):
    resumen = cargar(api)
    correccion = resumen.plan.correcciones[0]
    mes = api.get("/costos-fijos", params={"periodo": correccion.periodo}).json()
    nuevos = [g for g in mes["gastos"] if g["reemplaza_a"]]
    assert len(nuevos) == 1 and float(nuevos[0]["monto_ars_del_mes"]) == float(correccion.monto)
    original = next(g for g in resumen.plan.gastos if g.clave == correccion.clave_gasto)
    assert sum(1 for g in mes["gastos"] if g["concepto"] == original.concepto) == 1
    assert "EJEMPLO" in nuevos[0]["nota_fuente"] and nuevos[0]["ficticio"] is False
    # the replaced row is kept, only it no longer counts
    assert api.session.scalar(select(func.count()).select_from(GastoPeriodo).where(
        GastoPeriodo.periodo == correccion.periodo, GastoPeriodo.concepto == original.concepto)) == 2


def test_everything_it_creates_is_marked_and_the_seed_rows_stay_untouched(api):
    sembradas = {g.codigo: (g.monto_ars_del_mes, g.reemplaza_a_id) for g in api.session.scalars(select(GastoPeriodo))}
    cargar(api)
    s = api.session
    assert not [g for g in s.scalars(select(GastoPeriodo)) if g.codigo not in sembradas and "EJEMPLO" not in g.nota_fuente]
    assert not [d for d in s.scalars(select(TipoCambio)) if d.fuente != "EXCEL_VIEJO" and "EJEMPLO" not in d.nota]
    assert not [p for p in s.scalars(select(PrecioMaterial)) if p.nota_fuente and "EJEMPLO" not in p.nota_fuente
                and p.codigo not in {"PRE-%04d" % n for n in range(1, 12)}]
    assert not [o for o in s.scalars(select(OrdenFabricacion)) if "EJEMPLO" not in o.nota]
    assert not [i for i in s.scalars(select(OrdenItem)) if "EJEMPLO" not in i.nota]
    assert not [p for p in s.scalars(select(Producto)) if "EJEMPLO" not in p.nota]
    assert all("EJEMPLO" in c.nota for c in s.scalars(select(Color)))
    for codigo, (monto, reemplaza) in sembradas.items():
        fila = s.scalar(select(GastoPeriodo).where(GastoPeriodo.codigo == codigo))
        assert (fila.monto_ars_del_mes, fila.reemplaza_a_id) == (monto, reemplaza)


def test_a_month_that_already_has_its_own_fixed_costs_is_left_alone(api):
    # The seed already loaded 2026-10 with its own rows: the loader neither duplicates nor sums on top of them.
    propios = servicios.costos_fijos(api.session, "2026-10")["gastos"]
    assert propios, "the migrated seed must carry the fixed costs of 2026-10"
    resumen = ce.cargar_ejemplo(api.session, "2026-11", date(2026, 11, 4))
    assert servicios.costos_fijos(api.session, "2026-10")["gastos"] == propios
    assert any("2026-10" in aviso for aviso in resumen.avisos)


def test_the_cost_of_every_example_product_can_be_computed(api):
    cargar(api)
    productos = api.session.scalars(select(Producto).where(Producto.nota.like("EJEMPLO%"))).all()
    assert len(productos) >= 6
    for producto in productos:
        ficha = api.get(f"/productos/{producto.codigo}").json()
        assert ficha["costo_hoy"] is not None, producto.codigo


def test_workshop_lots_keep_asked_and_paid_prices_apart(api):
    cargar(api)
    cerrados = [o for o in api.get("/ordenes", params={"donde": "EXTERNA", "estado": "CERRADA"}).json()
                if "EJEMPLO" in (o["nota"] or "")]
    assert cerrados
    detalle = api.get(f"/ordenes/{cerrados[0]['codigo']}").json()
    assert all(0 < float(i["pagado"]) < float(i["cotizado"]) for i in detalle["items"])
    assert [e["estado"] for e in detalle["estados"]][-1] == "CERRADA"
