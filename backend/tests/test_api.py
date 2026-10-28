"""HTTP layer without a database: auth is fail-closed and routers only call the service layer."""

from datetime import date
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import api, servicios
from backend.auth import Usuario, get_verifier, require_user
from backend.database import get_session
from backend.main import app

RUTAS = sorted(
    (method, route.path)
    for route in api.router.routes if isinstance(route, APIRoute)
    for method in route.methods
)


@pytest.fixture(autouse=True)
def sin_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def con_usuario():
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba"))
    return TestClient(app), session


def test_the_router_exposes_every_documented_endpoint():
    assert set(RUTAS) >= {
        ("GET", "/productos"), ("GET", "/productos/{codigo}"), ("GET", "/modelos"), ("GET", "/materiales"),
        ("GET", "/precios"), ("GET", "/dolar"), ("GET", "/parametros"), ("GET", "/talleres"),
        ("GET", "/costos-fijos"), ("POST", "/productos"), ("POST", "/productos/{codigo}/extras"),
        ("POST", "/productos/{codigo}/componentes"), ("POST", "/productos/{codigo}/cotizaciones"),
        ("POST", "/precios"), ("POST", "/dolar"), ("POST", "/costos-fijos"), ("POST", "/ordenes"),
    }


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_every_route_is_closed_without_a_verifier(metodo, ruta):
    with TestClient(app) as client:
        response = client.request(metodo, ruta.replace("{codigo}", "PRD-0001"), json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado."}


@pytest.mark.parametrize("metodo, ruta", RUTAS)
def test_a_verifier_that_rejects_the_request_keeps_the_route_closed(metodo, ruta):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    with TestClient(app) as client:
        response = client.request(metodo, ruta.replace("{codigo}", "PRD-0001"), json={})
    assert response.status_code == 401


def test_require_user_has_no_default_verifier():
    assert get_verifier() is None
    assert app.dependency_overrides == {}
    assert require_user is not None


def test_existing_public_routes_stay_public():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/demo/resources").status_code == 200
        assert client.get("/db/estado").status_code == 503  # no database, but not 401


def test_money_is_returned_as_strings_not_floats(monkeypatch):
    client, _ = con_usuario()
    monkeypatch.setattr(servicios, "listar_dolar", lambda session: [
        {"fecha": date(2026, 9, 1), "ars_por_usd": D("1545.0000"), "fuente": "MANUAL", "tipo": None, "nota": None},
    ])
    response = client.get("/dolar")
    assert response.status_code == 200
    assert response.json()[0]["ars_por_usd"] == "1545.0000"


def test_service_errors_map_to_http_codes(monkeypatch):
    client, session = con_usuario()
    for error, status in ((servicios.NoEncontrado("x"), 404), (servicios.Conflicto("x"), 409), (servicios.DatosInvalidos("x"), 422)):
        def boom(session, *a, **k):
            raise error
        monkeypatch.setattr(servicios, "listar_talleres", boom)
        assert client.get("/talleres").status_code == status


def test_an_incomplete_quote_lists_its_warnings(monkeypatch):
    client, _ = con_usuario()

    def boom(session, *a, **k):
        raise servicios.CotizacionIncompleta(["Sin precio para MAT-FL01 a esa fecha"])
    monkeypatch.setattr(servicios, "guardar_cotizacion", boom)
    response = client.post("/productos/PRD-0001/cotizaciones", json={"tipo": "INICIAL"})
    assert response.status_code == 422
    assert response.json()["avisos"] == ["Sin precio para MAT-FL01 a esa fecha"]
    assert "Sin precio para MAT-FL01" in response.json()["detail"]


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/productos", {"modelo": "MOD-0001", "cuero": "MAT-CU01", "nombre": "x"}),
    ("/productos", {"modelo": "MOD-0001", "cuero": "MAT-CU01", "categoria": "Carteras"}),
    ("/productos/PRD-0001/cotizaciones", {"tipo": "INICIAL", "total_ars": "1"}),
    ("/productos/PRD-0001/cotizaciones", {"tipo": "INICIAL", "subtotal_etapas": "1"}),
    ("/costos-fijos", {"periodo": "2026-10", "concepto": "x", "fabrica_o_tienda": "FABRICA",
                       "categoria": "OTROS", "total_fabrica": "1"}),
    ("/precios", {"material": "MAT-CU01", "precio": "1", "moneda": "USD", "unidad_del_precio": "m2",
                  "vigente_desde": "2026-10-01", "codigo": "PRE-9999"}),
])
def test_calculated_or_unknown_fields_are_rejected_before_reaching_the_service(monkeypatch, ruta, cuerpo):
    client, _ = con_usuario()
    for nombre in ("crear_producto", "guardar_cotizacion", "crear_gasto", "crear_precio"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post(ruta, json=cuerpo).status_code == 422


def test_invalid_period_is_rejected():
    client, _ = con_usuario()
    assert client.get("/costos-fijos", params={"periodo": "2026-13"}).status_code == 422
    assert client.get("/costos-fijos", params={"periodo": "octubre"}).status_code == 422
