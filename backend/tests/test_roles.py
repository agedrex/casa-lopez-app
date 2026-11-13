"""Roles admin / gerente / taller: legacy aliasing and the deny-by-default access matrix.

SUPUESTO: validar con Gerardo y Alejandro. The matrix below is the contract; `test_every_route_has_exactly_the_documented_roles`
fails if a new endpoint is added without a role gate or with a different one.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import servicios
from backend.auth import Usuario, get_verifier, require_role
from backend.database import get_session
from backend.main import app

SIN_PERMISO = {"detail": "No tenés permiso para esta acción."}
ADMIN = frozenset({"admin"})
PRODUCTOS = frozenset({"admin", "gerente"})
CORTE = frozenset({"admin", "taller"})
TODOS = frozenset({"admin", "gerente", "taller"})


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


# --- Legacy aliasing (S2): applied when the roles are READ ---------------------------------------------------------

@pytest.mark.parametrize("leido, esperado", [
    ("admin", {"admin"}), ("gerente", {"gerente"}), ("taller", {"taller"}),
    ("cotizador", {"admin"}), ("corte", {"taller"}), ("consulta", {"gerente"}),
    ("cotizador,consulta", {"admin", "gerente"}),  # the union, not the strongest one
    ("consulta, corte", {"gerente", "taller"}),
    (" cotizador , admin ", {"admin"}),  # the alias and its canonical name collapse
    ("gerente,taller", {"gerente", "taller"}),
    ("admin,otro", {"admin"}),  # unknown names are dropped
    ("otro", set()), ("", set()), (None, set()), (" , ", set()),
    ("ADMIN", set()),  # names are exact: a different spelling is not a role
])
def test_roles_are_normalized_when_read(leido, esperado):
    assert Usuario(id="u", role=leido).roles == frozenset(esperado)


@pytest.mark.parametrize("leido, rutas", [
    ("cotizador", [("GET", "/panel/costos"), ("POST", "/productos"), ("GET", "/voz/estado")]),
    ("corte", [("GET", "/cueros"), ("POST", "/cueros/PZC-1/cortes")]),
    ("consulta", [("GET", "/productos"), ("GET", "/grilla")]),
])
def test_a_legacy_role_passes_the_gates_of_its_new_name(leido, rutas):
    cliente = _cliente(leido)
    for metodo, ruta in rutas:
        assert _estado(cliente, metodo, ruta) not in (401, 403), (leido, metodo, ruta)


def test_legacy_consulta_and_corte_keep_no_more_than_their_new_role():
    assert _estado(_cliente("consulta"), "GET", "/costos-fijos") == 403
    assert _estado(_cliente("consulta"), "GET", "/voz/estado") == 403
    assert _estado(_cliente("corte"), "GET", "/costos-fijos") == 403
    assert _estado(_cliente("corte"), "POST", "/productos") == 403


def test_a_user_with_only_unknown_roles_is_refused_where_a_role_is_required():
    for role in ("otro", "superadmin", "x,y", "", None):
        cliente = _cliente(role)
        for metodo, ruta in (("GET", "/materiales"), ("GET", "/productos"), ("POST", "/productos"), ("GET", "/voz/estado")):
            respuesta = cliente.request(metodo, ruta, json={} if metodo == "POST" else None)
            assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO, (role, metodo, ruta)


def test_require_role_accepts_legacy_names_in_its_arguments():
    assert require_role("cotizador").roles_permitidos == frozenset({"admin"})
    assert require_role("corte", "consulta").roles_permitidos == frozenset({"taller", "gerente"})


# --- The matrix (S3) --------------------------------------------------------------------------------------------------

ACCESO: dict[tuple[str, str], frozenset[str]] = {
    # Product and quote data: admin and gerente. /materiales has no prices, so every role reads it.
    ("GET", "/productos"): TODOS,  # taller: the "alcanza" selector of the cut pages and the product list
    ("GET", "/productos/conteo"): TODOS,  # taller: the pagination of that list (the sheet itself stays admin / gerente)
    ("GET", "/productos/{codigo}"): TODOS,
    ("GET", "/productos/{codigo}/rentabilidad"): PRODUCTOS,
    ("GET", "/productos/{codigo}/precio-sugerido"): PRODUCTOS,
    ("GET", "/productos/{codigo}/precio-venta"): PRODUCTOS,
    ("GET", "/grilla"): PRODUCTOS,
    ("GET", "/catalogos"): TODOS,
    ("GET", "/materiales"): TODOS,
    # What the corte / cueros / voz pages read.
    ("GET", "/cueros"): TODOS,
    ("GET", "/cueros/alcanza"): TODOS,
    ("GET", "/cueros/{codigo}"): TODOS,
    ("GET", "/colores"): TODOS,
    ("GET", "/ordenes"): TODOS,
    ("GET", "/ordenes/{codigo}"): TODOS,
    ("GET", "/ordenes/unidades-por-producto"): ADMIN,
    ("GET", "/voz/estado"): CORTE,
    # Admin only reads.
    ("GET", "/db/estado"): ADMIN,
    ("GET", "/productos/{codigo}/precios-talleres"): ADMIN,
    ("GET", "/modelos"): TODOS, ("GET", "/modelos/{codigo}"): TODOS,
    ("GET", "/precios"): TODOS, ("GET", "/precios/chequeo"): ADMIN,
    ("GET", "/categorias"): TODOS, ("GET", "/impuestos"): ADMIN, ("GET", "/dolar"): TODOS, ("GET", "/parametros"): ADMIN,
    ("GET", "/talleres"): PRODUCTOS, ("GET", "/talleres/{codigo}"): PRODUCTOS, ("GET", "/personas"): ADMIN,
    ("GET", "/talleres/{codigo}/historial"): ADMIN,
    ("GET", "/costos-fijos"): ADMIN, ("GET", "/costos-fijos/periodos"): ADMIN,
    ("GET", "/panel/costos"): PRODUCTOS, ("GET", "/panel/tendencia"): ADMIN,
    ("GET", "/fabricacion/casa-vs-taller"): ADMIN, ("GET", "/calidad"): PRODUCTOS,
    ("GET", "/sync/sheets/estado"): ADMIN, ("GET", "/sync/sheets/vista/{pestana}"): ADMIN,
    # Writes: admin only, except cutting and the voice interpreter.
    ("POST", "/cueros/{codigo}/cortes"): CORTE, ("POST", "/cueros/{codigo}/sobrante"): CORTE,
    ("POST", "/voz/interpretar"): CORTE,
    # Consumption forms: everybody reads (the service hides BORRADOR / VALIDADO from taller), admin and taller edit the rows
    # and complete, the rest is admin only.
    ("GET", "/formularios"): TODOS, ("GET", "/formularios/{codigo}"): TODOS,
    ("PUT", "/formularios/{codigo}"): CORTE, ("POST", "/formularios/{codigo}/completar"): CORTE,
    **{("POST", ruta): ADMIN for ruta in (
        "/productos/nuevo", "/formularios", "/formularios/{codigo}/enviar", "/formularios/{codigo}/devolver", "/formularios/{codigo}/validar",
        "/formularios/{codigo}/duplicar")},
    # The only write the voice grants a taller: the price a workshop quoted or was paid for a lot line.
    ("POST", "/ordenes/{codigo}/items/{item}/precios"): CORTE,
    **{("POST", ruta): ADMIN for ruta in (
        "/cueros", "/productos", "/productos/{codigo}/precio-venta", "/productos/{codigo}/extras",
        "/productos/{codigo}/componentes", "/productos/{codigo}/cotizaciones", "/cvu/escenario", "/precios", "/dolar",
        "/dolar/actualizar-bna", "/costos-fijos", "/costos-fijos/{codigo}/monto", "/costos-fijos/{codigo}/corregir",
        "/costos-fijos/{codigo}/anular", "/costos-fijos/copiar", "/ordenes", "/ordenes/{codigo}/estado", "/ordenes/{codigo}/items",
        "/talleres", "/talleres/{codigo}/activo", "/parametros/{codigo}",
        "/personas", "/personas/{codigo}/activo", "/colores", "/categorias", "/modelos", "/modelos/{codigo}/validado",
        "/impuestos", "/impuestos/{codigo}/alicuota", "/impuestos/{codigo}/activo",
        "/modelos/{codigo}/consumos", "/sync/sheets", "/costos-fijos/lote", "/modelos/consumos/lote")},
    # Suppliers: gerente reads (Abastecimiento), the invoice file and every write stay admin only.
    ("GET", "/reventa"): ADMIN, ("GET", "/reventa/{codigo}"): ADMIN,
    ("GET", "/proveedores"): PRODUCTOS, ("GET", "/proveedores/{codigo}"): PRODUCTOS,
    ("GET", "/proveedores/{codigo}/documentos"): PRODUCTOS, ("GET", "/documentos-proveedor/{id}/archivo"): ADMIN,
    ("GET", "/proveedores/{codigo}/materiales"): PRODUCTOS, ("GET", "/proveedores/{codigo}/pedidos"): PRODUCTOS,
    **{("POST", ruta): ADMIN for ruta in (
        "/reventa", "/reventa/lote", "/reventa/{codigo}/activo", "/reventa/{codigo}/compras",
        "/proveedores", "/proveedores/{codigo}", "/proveedores/{codigo}/activo", "/proveedores/{codigo}/documentos",
        "/proveedores/{codigo}/precios", "/proveedores/{codigo}/pedidos",
        "/documentos-proveedor/{id}/ocr", "/documentos-proveedor/{id}/datos")},
}
# Open on purpose: the health check of the deploy and the stage catalog of routers.py, which carries no business data
# (stage codes). `/db/estado` shows the Alembic revision and the table count, so it is admin only.
PUBLICAS = {("GET", "/api/health"), ("GET", "/catalogo/etapas")}


def _api_routes(rutas=None):
    """Every APIRoute of the app, also the ones of included routers (FastAPI wraps them in `_IncludedRouter`)."""
    for ruta in app.routes if rutas is None else rutas:
        if isinstance(ruta, APIRoute):
            yield ruta
        elif hasattr(ruta, "original_router"):
            yield from _api_routes(ruta.original_router.routes)


def _rutas():
    return sorted((metodo, ruta.path) for ruta in _api_routes() for metodo in ruta.methods)


def _roles_de(ruta: APIRoute) -> set[frozenset[str]]:
    """The role sets of every `require_role` gate on the route (router-level dependencies included)."""
    pendientes, vistas = list(ruta.dependant.dependencies), set()
    while pendientes:
        dependencia = pendientes.pop()
        permitidos = getattr(dependencia.call, "roles_permitidos", None)
        if permitidos is not None:
            vistas.add(permitidos)
        pendientes.extend(dependencia.dependencies)
    return vistas


def _cliente(role, session=None):
    session = session or MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u", role=role))
    return TestClient(app, raise_server_exceptions=False)


def _estado(cliente, metodo, ruta):
    return cliente.request(metodo, ruta.replace("{codigo}", "X-1").replace("{item}", "I-1").replace("{pestana}", "Dolar").replace("{id}", "7"),
                           json={} if metodo == "POST" else None).status_code


def test_every_route_has_exactly_the_documented_roles():
    documentadas = set(ACCESO) | PUBLICAS
    assert set(_rutas()) == documentadas  # a new route must be added to the matrix (and so be decided)
    for ruta in _api_routes():
        for metodo in ruta.methods:
            clave = (metodo, ruta.path)
            if clave in PUBLICAS:
                assert _roles_de(ruta) == set(), clave
            else:
                assert _roles_de(ruta) == {ACCESO[clave]}, clave  # exactly one gate, with the documented roles


@pytest.mark.parametrize("role", ["gerente", "taller", "otro", None, "consulta,corte"])
def test_admin_only_routes_refuse_everyone_else_without_calling_the_service(monkeypatch, role):
    session = MagicMock()
    cliente = _cliente(role, session)
    # Whatever the route is, the gate answers before anything reaches the service layer or the database.
    for nombre in dir(servicios):
        if callable(getattr(servicios, nombre)) and not nombre.startswith("_") and nombre.islower():
            monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    for (metodo, ruta), permitidos in ACCESO.items():
        if Usuario(id="u", role=role).roles & permitidos:
            continue
        respuesta = cliente.request(
            metodo, ruta.replace("{codigo}", "X-1").replace("{item}", "I-1").replace("{pestana}", "Dolar").replace("{id}", "7"),
            json={} if metodo == "POST" else None)
        assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO, (role, metodo, ruta)
    session.commit.assert_not_called()


@pytest.mark.parametrize("role, rutas", [
    ("gerente", [("GET", "/productos"), ("GET", "/productos/conteo"), ("GET", "/productos/X-1"),
                 ("GET", "/productos/X-1/rentabilidad"), ("GET", "/productos/X-1/precio-venta"), ("GET", "/grilla"),
                 ("GET", "/catalogos"), ("GET", "/materiales"),
                 ("GET", "/panel/costos"), ("GET", "/calidad"), ("GET", "/dolar"),
                 ("GET", "/ordenes"), ("GET", "/ordenes/LOT-1"), ("GET", "/cueros"), ("GET", "/cueros/PZC-1"),
                 ("GET", "/talleres"), ("GET", "/talleres/T-1"), ("GET", "/proveedores"), ("GET", "/proveedores/PRV-1"),
                 ("GET", "/proveedores/PRV-1/pedidos"), ("GET", "/formularios"), ("GET", "/formularios/FCO-0001")]),
    ("taller", [("GET", "/productos"), ("GET", "/productos/conteo"), ("GET", "/materiales"), ("GET", "/cueros"), ("GET", "/cueros/PZC-1"),
                ("GET", "/cueros/alcanza?producto=P&cantidad=1"), ("GET", "/colores"), ("GET", "/ordenes"),
                ("GET", "/ordenes/LOT-1"), ("GET", "/voz/estado"),
                ("GET", "/productos/X-1"),
                ("GET", "/modelos"), ("GET", "/modelos/MOD-1"), ("GET", "/precios"), ("GET", "/categorias"), ("GET", "/catalogos"), ("GET", "/dolar"),
                ("POST", "/cueros/PZC-1/cortes"), ("POST", "/cueros/PZC-1/sobrante"), ("POST", "/voz/interpretar"),
                ("GET", "/formularios"), ("GET", "/formularios/FCO-0001"), ("PUT", "/formularios/FCO-0001"),
                ("POST", "/formularios/FCO-0001/completar")]),
    ("admin", [("GET", "/panel/costos"), ("GET", "/costos-fijos"), ("GET", "/ordenes"), ("GET", "/productos"),
               ("GET", "/cueros"), ("GET", "/voz/estado"), ("POST", "/cvu/escenario"), ("POST", "/ordenes"),
               ("POST", "/productos"), ("POST", "/cueros/PZC-1/cortes"), ("POST", "/formularios"),
               ("POST", "/proveedores/PRV-1/pedidos"), ("GET", "/proveedores/PRV-1/pedidos"), ("PUT", "/formularios/FCO-0001"), ("POST", "/formularios/FCO-0001/validar")]),
])
def test_each_role_passes_the_gate_of_its_allowed_set(role, rutas):
    cliente = _cliente(role)
    for metodo, ruta in rutas:
        # Past the gate the handler may fail on the mock session; only a 401/403 means "refused".
        assert _estado(cliente, metodo, ruta) not in (401, 403), (role, metodo, ruta)


def test_taller_is_still_refused_on_the_panel_reads_that_gerente_now_has():
    cliente = _cliente("taller")
    for ruta in ("/panel/costos", "/calidad"):
        respuesta = cliente.get(ruta)
        assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO, ruta


@pytest.mark.parametrize("metodo, ruta", [
    ("GET", "/panel/tendencia"), ("GET", "/costos-fijos"), ("POST", "/cvu/escenario"), ("POST", "/productos"),
])
@pytest.mark.parametrize("role", ["gerente", "taller"])
def test_gerente_and_taller_are_refused_on_the_representative_admin_routes(metodo, ruta, role):
    cliente = _cliente(role)
    respuesta = cliente.request(metodo, ruta, json={} if metodo == "POST" else None)
    assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO


@pytest.mark.parametrize("metodo, ruta", [
    ("GET", "/productos/X-1/precios-talleres"), ("GET", "/grilla"), ("POST", "/productos"),
    ("GET", "/productos/X-1/rentabilidad"), ("GET", "/productos/X-1/precio-venta"), ("GET", "/talleres/TAL-1/historial"),
    ("POST", "/productos/X-1/cotizaciones"), ("POST", "/modelos"), ("GET", "/proveedores"), ("GET", "/talleres"),
])
def test_taller_quotes_read_only_and_stays_out_of_the_rest_of_the_products(monkeypatch, metodo, ruta):
    # Taller reads what it needs to quote or assemble a product; writes, the grid and supplier data stay closed.
    for nombre in dir(servicios):
        if callable(getattr(servicios, nombre)) and not nombre.startswith("_") and nombre.islower():
            monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    respuesta = _cliente("taller").request(metodo, ruta, json={} if metodo == "POST" else None)
    assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO


def test_the_product_count_is_still_closed_without_a_role():
    for role in ("otro", "", None):
        respuesta = _cliente(role).get("/productos/conteo")
        assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO


def test_the_public_routes_stay_open_without_a_session():
    with TestClient(app) as cliente:  # the lifespan sets `app.state.db_engine`
        assert cliente.get("/api/health").status_code == 503  # no database, but not 401
        assert cliente.get("/catalogo/etapas").status_code == 503  # no database, but not 401


def test_the_demo_resources_route_is_gone_for_everyone():
    for role in ("admin", "gerente", "taller", None):
        assert _cliente(role).get("/api/demo/resources").status_code == 404
    assert TestClient(app).get("/api/demo/resources").status_code == 404


def test_db_estado_is_closed_without_a_session():
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    respuesta = TestClient(app).get("/db/estado")
    assert respuesta.status_code == 401 and respuesta.json() == {"detail": "No autenticado."}
    assert TestClient(app).get("/db/estado").status_code == 401  # no verifier configured: fail-closed


@pytest.mark.parametrize("role", ["gerente", "taller", "otro", None])
def test_db_estado_refuses_every_role_but_admin(role):
    session = MagicMock()
    respuesta = _cliente(role, session).get("/db/estado")
    assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO
    session.execute.assert_not_called()


def test_db_estado_answers_the_admin():
    session = MagicMock()
    session.execute.return_value.one.return_value = ("0004_semillas_v3", 25)
    respuesta = _cliente("admin", session).get("/db/estado")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "alembic_revision": "0004_semillas_v3", "tablas_costos": 25}


@pytest.mark.parametrize("metodo, ruta", [(m, r) for m, r in ACCESO])
def test_no_session_is_still_401_not_403(metodo, ruta):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    respuesta = TestClient(app).request(
        metodo, ruta.replace("{codigo}", "X-1").replace("{item}", "I-1").replace("{pestana}", "Dolar").replace("{id}", "7"),
        json={} if metodo == "POST" else None)
    assert respuesta.status_code == 401 and respuesta.json() == {"detail": "No autenticado."}
