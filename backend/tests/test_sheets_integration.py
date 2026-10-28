"""Sheet export against the migrated and seeded local PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back. No Google call is made: only the dry run and the
builders are exercised, so the check is that the real loaders produce the shapes the tabs expect.
"""

from datetime import datetime
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import api as api_module
from backend import servicios
from backend import sheets_client
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Material, Modelo, Parametro, Producto, Taller
from backend.sheets_export import NOMBRES_DE_PESTANAS, FuenteSQL, construir_tabs

AHORA = datetime.fromisoformat("2026-10-28T12:00:00-03:00")


@pytest.fixture
def sesion(local_postgres):
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def api(sesion, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for nombre in sheets_client.VARIABLES:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr(api_module, "_ESTADO_SYNC", api_module.EstadoDeSincronizacion())
    app.dependency_overrides[get_session] = lambda: sesion
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="admin-de-prueba", role="admin"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def tabs_por_nombre(sesion):
    return {t.name: t for t in construir_tabs(FuenteSQL(sesion), generado_en=AHORA, version="test")}


def contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


def test_the_seeded_database_builds_every_tab_with_the_right_row_counts(sesion):
    tabs = tabs_por_nombre(sesion)
    assert tuple(tabs) == NOMBRES_DE_PESTANAS
    for nombre, tab in tabs.items():
        assert tab.headers and all(len(fila) == len(tab.headers) for fila in tab.rows), nombre
        assert all(type(c) in (str, D) for fila in tab.rows for c in fila), nombre
    assert len(tabs["Modelos"].rows) == contar(sesion, Modelo) > 0
    assert len(tabs["Materiales"].rows) == contar(sesion, Material) > 0
    assert len(tabs["Parametros"].rows) == contar(sesion, Parametro) > 0
    assert len(tabs["Talleres"].rows) == contar(sesion, Taller)
    assert len(tabs["Productos"].rows) == len(tabs["Catalogo"].rows) == contar(sesion, Producto)
    assert len(tabs["Dolar"].rows) >= 1 and len(tabs["Precios"].rows) > 0 and len(tabs["Costos_Fijos"].rows) > 0


def test_cost_columns_are_the_ones_the_service_calculated_not_recalculated(sesion, api):
    codigo = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03",
    }).json()["codigo"]
    assert api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"}).status_code == 201

    # Seeded dollar of 2026-09-01 is older than the flex price (09-03): no cost today yet, only warnings.
    ficha = api.get(f"/productos/{codigo}").json()
    assert ficha["costo_hoy"] is None
    tabs = tabs_por_nombre(sesion)
    sin_costo = next(dict(zip(tabs["Catalogo"].headers, f)) for f in tabs["Catalogo"].rows if f[0] == codigo)
    assert sin_costo["CV hoy ARS"] == "" and sin_costo["Alertas"] == "; ".join(ficha["avisos"]) != ""
    assert sin_costo["Cotización inicial ARS"] == D(ficha["cotizaciones"][0]["total_ars"])

    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    ficha = api.get(f"/productos/{codigo}").json()
    tabs = tabs_por_nombre(sesion)

    catalogo = next(dict(zip(tabs["Catalogo"].headers, f)) for f in tabs["Catalogo"].rows if f[0] == codigo)
    assert catalogo["CV hoy ARS"] == D(ficha["costo_hoy"]["total_ars"])
    assert catalogo["CV hoy USD"] == D(ficha["costo_hoy"]["total_usd"])
    assert catalogo["Cotización inicial ARS"] == D(ficha["cotizaciones"][0]["total_ars"])
    assert catalogo["Estado del ciclo"] == ficha["estado_del_ciclo"] and catalogo["Kit"] == "NO"

    variables = next(dict(zip(tabs["Costos_Variables"].headers, f)) for f in tabs["Costos_Variables"].rows if f[0] == codigo)
    for etapa, monto in ficha["costo_hoy"]["etapas"].items():
        assert variables[etapa] == D(monto), etapa
    assert variables["CV por unidad ARS"] == D(ficha["costo_hoy"]["total_ars"])

    guardadas = [dict(zip(tabs["Cotizaciones"].headers, f)) for f in tabs["Cotizaciones"].rows if f[0] == codigo]
    assert len(guardadas) == 1 and guardadas[0]["Tipo"] == "INICIAL"
    assert guardadas[0]["Total ARS"] == D(ficha["cotizaciones"][0]["total_ars"])
    assert guardadas[0]["Producto (nombre)"] == ficha["nombre"]


def test_the_dry_run_over_http_counts_every_tab_and_stays_local(sesion, api):
    api.post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA"})
    respuesta = api.post("/sync/sheets", json={"simular": True})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["simulacion"] is True and datos["configurado"] is False
    por_nombre = {p["nombre"]: p["filas"] for p in datos["pestanas"]}
    assert set(por_nombre) == set(NOMBRES_DE_PESTANAS)
    assert por_nombre["Catalogo"] == 1 and por_nombre["Modelos"] == contar(sesion, Modelo)
    vista = api.get("/sync/sheets/vista/Modelos").json()
    assert vista["mostradas"] == 50 and vista["total_filas"] == contar(sesion, Modelo)
    assert api.get("/sync/sheets/estado").json()["ultima"]["ok"] is True


def test_the_quality_tab_matches_the_quality_report(sesion):
    informe = servicios.calidad_de_datos(sesion, hoy=AHORA.date())
    tabs = tabs_por_nombre(sesion)
    assert len(tabs["Calidad"].rows) == informe["resumen"]["total"]
