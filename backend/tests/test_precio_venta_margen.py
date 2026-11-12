"""The margin a person used is saved next to the sale price (a fraction: 0.30 = 30 %); NULL = price typed by hand."""

import runpy
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import PrecioVenta

from test_migrations import VERSIONS, load_revision


def sesion_con_producto():
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(id=7, codigo="PRD-0001")
    return session


# --- Service ------------------------------------------------------------------------------------------------------

def test_the_margin_is_stored_with_the_price_and_returned():
    session = sesion_con_producto()
    r = servicios.guardar_precio_de_venta(session, "PRD-0001", precio_ars=D("214.2900"), margen=D("0.300"), hoy=date(2026, 11, 12))
    fila = session.add.call_args.args[0]
    assert isinstance(fila, PrecioVenta) and fila.margen == D("0.300")
    assert r["margen"] == D("0.300")


def test_without_a_margin_the_price_is_saved_as_before_with_a_null_margin():
    session = sesion_con_producto()
    r = servicios.guardar_precio_de_venta(session, "PRD-0001", precio_ars=D("10"), hoy=date(2026, 11, 12))
    fila = session.add.call_args.args[0]
    assert fila.margen is None and r["margen"] is None
    assert r["precio_ars"] == D("10") and r["producto"] == "PRD-0001"


def test_the_history_carries_the_saved_margin_of_each_price():
    session = sesion_con_producto()
    con = PrecioVenta(producto_id=7, precio_ars=D("120"), vigente_desde=date(2026, 11, 1), creado_por=None, nota=None, margen=D("0.250"))
    sin = PrecioVenta(producto_id=7, precio_ars=D("100"), vigente_desde=date(2026, 10, 1), creado_por=None, nota=None)
    session.scalars.return_value.all.return_value = [con, sin]
    historial = servicios.listar_precios_de_venta(session, "PRD-0001")
    assert [fila["margen"] for fila in historial] == [D("0.250"), None]


# --- API ----------------------------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="user-42", role="admin"))
    yield TestClient(app)
    app.dependency_overrides.clear()


def falso_servicio(monkeypatch):
    visto = {}

    def falso(session, codigo, **kwargs):
        visto.update(codigo=codigo, **kwargs)
        return {"producto": codigo, "precio_ars": kwargs["precio_ars"], "vigente_desde": date(2026, 11, 12), "nota": kwargs["nota"],
                "creado_por": kwargs["quien"], "creado_en": None, "margen": kwargs["margen"]}
    monkeypatch.setattr(servicios, "guardar_precio_de_venta", falso)
    return visto


def test_posting_a_margin_reaches_the_service_and_comes_back_as_a_string(client, monkeypatch):
    visto = falso_servicio(monkeypatch)
    response = client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "214.29", "margen": "0.300"})
    assert response.status_code == 201
    assert visto["margen"] == D("0.300")
    assert response.json()["margen"] == "0.300"


def test_posting_without_a_margin_keeps_working_and_the_margin_is_null(client, monkeypatch):
    visto = falso_servicio(monkeypatch)
    response = client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "10"})
    assert response.status_code == 201
    assert visto["margen"] is None
    assert response.json()["margen"] is None


def test_an_explicit_null_margin_is_accepted(client, monkeypatch):
    visto = falso_servicio(monkeypatch)
    assert client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "10", "margen": None}).status_code == 201
    assert visto["margen"] is None


@pytest.mark.parametrize("margen", ["1", "-0.1", "1.5", "0.3001", "abc"])
def test_a_margin_outside_zero_to_below_one_or_with_too_many_decimals_is_a_422(client, monkeypatch, margen):
    monkeypatch.setattr(servicios, "guardar_precio_de_venta", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "10", "margen": margen}).status_code == 422


@pytest.mark.parametrize("margen", ["0", "0.999"])
def test_the_margin_bounds_zero_and_just_below_one_are_accepted(client, monkeypatch, margen):
    visto = falso_servicio(monkeypatch)
    assert client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "10", "margen": margen}).status_code == 201
    assert visto["margen"] == D(margen)


# --- Model and migration ------------------------------------------------------------------------------------------

def test_the_model_column_is_a_nullable_fraction_with_a_range_check():
    columna = PrecioVenta.__table__.c.margen
    assert columna.nullable and (columna.type.precision, columna.type.scale) == (6, 3)
    checks = {c.name: str(c.sqltext) for c in PrecioVenta.__table__.constraints if isinstance(c, CheckConstraint)}
    assert checks["ck_precio_venta_margen_en_rango"] == "margen IS NULL OR (margen >= 0 AND margen < 1)"


def test_the_revision_adds_the_column_and_the_check_and_the_downgrade_drops_both(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    runpy.run_path(str(VERSIONS / "0006_precio_venta.py"))["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0015_precio_venta_margen.py"))
    assert revision["revision"] == "0015_precio_venta_margen" and revision["down_revision"] == "0014_gastos_venta_pct"
    revision["upgrade"]()
    precio = operations.metadata.tables["costos.precio_venta"]
    assert precio.c.margen.nullable and str(precio.c.margen.type) == "NUMERIC(6, 3)"
    assert {c.name for c in precio.constraints if isinstance(c, CheckConstraint)} >= {"ck_precio_venta_margen_en_rango"}
    revision["downgrade"]()
    assert operations.dropped_constraints == ["ck_precio_venta_margen_en_rango"]
    assert operations.dropped_columns == [("costos", "precio_venta", "margen")]
    assert "lost" in revision["__doc__"]
