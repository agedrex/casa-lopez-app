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


def con_usuario(role: str | None = "cotizador"):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role=role))
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


# --- Roles: every write needs admin or cotizador; reads stay open to any signed-in user ----------------------

# The admin area (T5c) writes are admin only; test_admin.py covers their gate. Every other POST is admin or cotizador.
# POST /sync/sheets (T6) is admin only too; test_sheets_api.py covers its gate.
SOLO_ADMIN = {"/parametros/{codigo}", "/personas", "/personas/{codigo}/activo", "/colores", "/categorias",
              "/modelos/{codigo}/consumos", "/sync/sheets"}
ESCRITURAS = [(m, r) for m, r in RUTAS if m == "POST" and r not in SOLO_ADMIN]
LECTURAS = [(m, r) for m, r in RUTAS if m == "GET"]
SIN_PERMISO = {"detail": "No tenés permiso para esta acción."}


def test_every_write_route_is_covered_by_the_role_tests():
    assert len(ESCRITURAS) == 18 and {r for _, r in ESCRITURAS} >= {"/modelos", "/modelos/{codigo}/validado", "/voz/interpretar",
        "/productos", "/precios", "/dolar", "/dolar/actualizar-bna", "/ordenes", "/talleres", "/talleres/{codigo}/activo",
        "/ordenes/{codigo}/estado", "/ordenes/{codigo}/items", "/ordenes/{codigo}/items/{item}/precios",
        "/costos-fijos/{codigo}/monto"}


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS)
@pytest.mark.parametrize("role", ["consulta", None, "otro"])
def test_a_user_without_a_writing_role_gets_403_on_every_post(monkeypatch, metodo, ruta, role):
    client, session = con_usuario(role)
    monkeypatch.setattr(servicios, "crear_producto", lambda *a, **k: pytest.fail("the service must not be called"))
    response = client.request(metodo, ruta.replace("{codigo}", "PRD-0001"), json={})
    assert response.status_code == 403
    assert response.json() == SIN_PERMISO
    session.commit.assert_not_called()


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS)
@pytest.mark.parametrize("role", ["admin", "cotizador", "consulta,cotizador"])
def test_admin_and_cotizador_pass_the_role_gate_on_every_post(monkeypatch, metodo, ruta, role):
    client, _ = con_usuario(role)
    if ruta == "/dolar/actualizar-bna":
        # Bodyless route: stub the service so the test never reaches bna.com.ar.
        def sin_fuente(*a, **k):
            raise servicios.FuenteNoDisponible("sin red en la prueba")
        monkeypatch.setattr(servicios, "actualizar_dolar_bna", sin_fuente)
        response = client.request(metodo, ruta, json={})
        assert response.status_code == 502  # past the gate: the service ran and its failure is mapped
        return
    response = client.request(metodo, ruta.replace("{codigo}", "PRD-0001"), json={})
    assert response.status_code == 422  # past the gate: the empty body is what is refused


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS)
def test_posts_without_a_session_stay_401_not_403(metodo, ruta):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    with TestClient(app) as client:
        response = client.request(metodo, ruta.replace("{codigo}", "PRD-0001"), json={})
    assert response.status_code == 401
    assert response.json() == {"detail": "No autenticado."}


@pytest.mark.parametrize("metodo, ruta", [(m, r) for m, r in LECTURAS if "{" not in r and r != "/productos/conteo"])
def test_reads_are_open_to_the_consulta_role(monkeypatch, metodo, ruta):
    client, session = con_usuario("consulta")
    # The heavy reads are covered against PostgreSQL; here only the gate matters, so the service answers an empty body.
    monkeypatch.setattr(servicios, "listar_ordenes", lambda *a, **k: [])
    monkeypatch.setattr(servicios, "casa_vs_taller", lambda *a, **k: {"talleres": [], "meses": []})
    monkeypatch.setattr(servicios, "periodos_de_costos_fijos", lambda *a, **k: {"vigente": None, "periodos": []})
    monkeypatch.setattr(servicios, "calidad_de_datos", lambda *a, **k: {
        "resumen": {"alta": 0, "media": 0, "baja": 0, "total": 0}, "grupos": []})
    session.execute.return_value.all.return_value = []
    session.execute.return_value.one.return_value = (0,)
    session.scalars.return_value = []
    session.scalar.return_value = "2026-10"
    response = client.get(ruta)
    assert response.status_code != 403 and response.status_code != 401


def test_the_new_reads_are_declared():
    assert {("GET", "/catalogos"), ("GET", "/productos/conteo"), ("GET", "/precios/chequeo")} <= set(RUTAS)
    assert {
        ("GET", "/ordenes"), ("GET", "/ordenes/{codigo}"), ("GET", "/fabricacion/casa-vs-taller"),
        ("GET", "/talleres/{codigo}"), ("GET", "/personas"), ("GET", "/costos-fijos/periodos"), ("GET", "/calidad"),
        ("GET", "/productos/{codigo}/precios-talleres"),
    } <= set(RUTAS)


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/talleres", {"nombre": "X", "codigo": "TAL-0099"}),
    ("/talleres", {"nombre": "X", "lotes": 3}),
    ("/ordenes/LOT-0001/estado", {"estado": "LISTA", "fecha": "2026-10-06", "periodo": "2026-10"}),
    ("/ordenes/LOT-0001/estado", {"estado": "LISTA"}),
    ("/ordenes/LOT-0001/items/LIT-0001/precios", {}),
    ("/ordenes/LOT-0001/items/LIT-0001/precios", {"pagado": "-1"}),
    ("/ordenes/LOT-0001/items/LIT-0001/precios", {"pagado": "1", "total_linea": "1"}),
    ("/costos-fijos/GF-0001/monto", {"monto_ars_del_mes": "-1"}),
    ("/costos-fijos/GF-0001/monto", {"monto_ars_del_mes": "1", "total_fabrica": "1"}),
])
def test_new_bodies_reject_calculated_or_invalid_fields_before_the_service(monkeypatch, ruta, cuerpo):
    client, _ = con_usuario()
    for nombre in ("crear_taller", "registrar_estado", "registrar_precios_item", "cargar_monto_de_gasto"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post(ruta, json=cuerpo).status_code == 422


def test_invalid_months_are_rejected_on_the_new_reads():
    client, _ = con_usuario()
    assert client.get("/fabricacion/casa-vs-taller", params={"hasta": "2026-13"}).status_code == 422
    assert client.get("/ordenes", params={"estado": "NADA"}).status_code == 422


def test_the_product_search_reaches_the_service(monkeypatch):
    client, _ = con_usuario("consulta")
    visto = {}

    def listar(session, limit, offset, q=None, categoria=None):
        visto.update(limit=limit, offset=offset, q=q, categoria=categoria)
        return []
    monkeypatch.setattr(servicios, "listar_productos", listar)
    assert client.get("/productos", params={"q": "cartera", "categoria": "Carteras", "limit": 5}).json() == []
    assert visto == {"limit": 5, "offset": 0, "q": "cartera", "categoria": "Carteras"}
    assert client.get("/productos").status_code == 200
    assert visto == {"limit": 100, "offset": 0, "q": None, "categoria": None}


def test_the_count_is_a_separate_route_so_the_list_keeps_its_shape(monkeypatch):
    client, _ = con_usuario("consulta")
    monkeypatch.setattr(servicios, "contar_productos", lambda session, q=None, categoria=None: 7)
    assert client.get("/productos/conteo", params={"q": "x"}).json() == {"total": 7}
