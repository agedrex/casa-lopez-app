"""Admin area (T5c): parameters, people, taxes, catalogs and models.

Pure rules and the HTTP gate first (no database), then the flows against the disposable local PostgreSQL
(skipped without TEST_DATABASE_URL, like test_api_integration.py).
"""

import logging
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import api as api_module
from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Modelo, Persona

# --- Pure rules ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("unidad, valor, texto", [
    ("%", D("0"), None), ("%", D("0.05"), None), ("%", D("1"), None),
    ("ARS/USD", D("1700"), None), ("m2", D("0.0001"), None), ("AAAA-MM", None, "2026-11"),
])
def test_valid_parameter_values_are_accepted(unidad, valor, texto):
    servicios.validar_valor_de_parametro(unidad, valor, texto)


@pytest.mark.parametrize("unidad, valor, texto, fragmento", [
    ("%", D("1.5"), None, "fracción"),
    ("%", D("5"), None, "0,05"),  # the person typed 5 meaning 5 %: the message says how to write it
    ("%", D("-0.1"), None, "fracción"),
    ("%", None, None, "valor"),
    ("%", D("0.1"), "x", "uno solo"),
    ("ARS/USD", D("0"), None, "mayor que 0"),
    ("ARS/USD", D("-5"), None, "mayor que 0"),
    ("m2", D("0"), None, "mayor que 0"),
    ("AAAA-MM", None, "2026-13", "AAAA-MM"),
    ("AAAA-MM", None, "octubre", "AAAA-MM"),
    ("AAAA-MM", None, "2026-1", "AAAA-MM"),
    ("AAAA-MM", D("2026"), None, "texto"),
    ("AAAA-MM", None, None, "AAAA-MM"),
    ("fecha", None, "2026-10-01", "no se puede editar"),
    (None, D("1"), None, "regla"),
    ("kg", D("1"), None, "regla"),
])
def test_invalid_parameter_values_are_refused_with_a_spanish_reason(unidad, valor, texto, fragmento):
    with pytest.raises(servicios.DatosInvalidos) as error:
        servicios.validar_valor_de_parametro(unidad, valor, texto)
    assert fragmento in str(error.value)


def test_the_state_text_keeps_the_prefix_the_quality_report_reads():
    assert servicios.texto_de_estado("Confirmado", None) == "Confirmado"
    assert servicios.texto_de_estado("Propuesta", "  a confirmar con Robert ") == "Propuesta: a confirmar con Robert"
    assert servicios.texto_de_estado("Pendiente", "") == "Pendiente"
    assert servicios.estado_de_parametro(servicios.texto_de_estado("Confirmado", "Robert 27/10")) is None
    assert servicios.estado_de_parametro(servicios.texto_de_estado("Pendiente", "x"))[0] == "media"
    assert servicios.estado_de_parametro(servicios.texto_de_estado("Propuesta", None))[0] == "media"


@pytest.mark.parametrize("nombre, codigo", [
    ("Portafolios", "CAT-PORT"), ("Zapatos de vestir", "CAT-ZAPA"), ("Riñoneras nuevas", "CAT-RINO"),
    ("Ñandú", "CAT-NAND"), ("  cinturones  ", "CAT-CINT"), ("Mochilas y morrales", "CAT-MOCH"),
    ("Pi", None), ("123", None), ("", None),
])
def test_category_code_follows_the_seed_convention_when_derivable(nombre, codigo):
    # SUPUESTO: validar. 15 of the 16 seeded categories are CAT- plus the first four letters of the name.
    assert servicios.codigo_de_categoria(nombre) == codigo


def test_closed_lists_match_the_database_check_constraints():
    persona = " ".join(str(c.sqltext) for c in Persona.__table__.constraints if hasattr(c, "sqltext"))
    modelo = " ".join(str(c.sqltext) for c in Modelo.__table__.constraints if hasattr(c, "sqltext"))
    for valor in servicios.PERSONA_ROLES + servicios.PERSONA_VINCULOS:
        assert f"'{valor}'" in persona
    for valor in servicios.TAMANOS + servicios.ORIGENES:
        assert f"'{valor}'" in modelo


# --- HTTP gate (no database) ----------------------------------------------------------------------------------

RUTAS = sorted(
    (method, route.path)
    for route in api_module.router.routes if isinstance(route, APIRoute)
    for method in route.methods
)
SOLO_ADMIN = [
    ("POST", "/parametros/{codigo}"), ("POST", "/personas"), ("POST", "/personas/{codigo}/activo"),
    ("POST", "/colores"), ("POST", "/categorias"), ("POST", "/modelos/{codigo}/consumos"),
]
ADMIN_O_COTIZADOR = [("POST", "/modelos"), ("POST", "/modelos/{codigo}/validado")]
LECTURAS_NUEVAS = [("GET", "/impuestos"), ("GET", "/colores"), ("GET", "/categorias"), ("GET", "/modelos/{codigo}")]


@pytest.fixture(autouse=True)
def sin_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def con_usuario(role):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", email="u@x.com", role=role))
    return TestClient(app), session


def ruta(path):
    return path.replace("{codigo}", "X-0001")


def test_the_new_endpoints_are_declared():
    assert set(SOLO_ADMIN + ADMIN_O_COTIZADOR + LECTURAS_NUEVAS) <= set(RUTAS)


@pytest.mark.parametrize("metodo, path", SOLO_ADMIN + ADMIN_O_COTIZADOR + LECTURAS_NUEVAS)
def test_the_new_endpoints_are_closed_without_a_session(metodo, path):
    with TestClient(app) as client:
        response = client.request(metodo, ruta(path), json={})
    assert response.status_code == 401 and response.json() == {"detail": "No autenticado."}


@pytest.mark.parametrize("metodo, path", SOLO_ADMIN)
@pytest.mark.parametrize("role", ["cotizador", "consulta", None, "cotizador,consulta"])
def test_admin_only_endpoints_refuse_every_other_role(monkeypatch, metodo, path, role):
    client, session = con_usuario(role)
    for nombre in ("cambiar_parametro", "crear_persona", "cambiar_activo_persona", "crear_color", "crear_categoria",
                   "cambiar_consumos"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    response = client.request(metodo, ruta(path), json={})
    assert response.status_code == 403
    assert response.json() == {"detail": "No tenés permiso para esta acción."}
    session.commit.assert_not_called()


@pytest.mark.parametrize("metodo, path", SOLO_ADMIN)
def test_admin_passes_the_gate_of_the_admin_only_endpoints(metodo, path):
    client, _ = con_usuario("admin")
    assert client.request(metodo, ruta(path), json={}).status_code == 422  # past the gate: the empty body is refused


@pytest.mark.parametrize("metodo, path", ADMIN_O_COTIZADOR)
@pytest.mark.parametrize("role, status", [("admin", 422), ("cotizador", 422), ("consulta", 403), (None, 403)])
def test_model_creation_and_validation_need_a_writing_role(metodo, path, role, status):
    client, _ = con_usuario(role)
    assert client.request(metodo, ruta(path), json={}).status_code == status


@pytest.mark.parametrize("path, cuerpo", [
    ("/parametros/ARREGLOS_PCT", {"valor": "0.05", "fuente_estado": "Confirmado", "codigo": "X"}),
    ("/parametros/ARREGLOS_PCT", {"valor": "0.05", "fuente_estado": "Confirmado", "unidad": "ARS"}),
    ("/parametros/ARREGLOS_PCT", {"valor": "0.05", "fuente_estado": "Calculado"}),
    ("/parametros/ARREGLOS_PCT", {"valor": "0.05"}),
    ("/parametros/ARREGLOS_PCT", {"valor": "0.12345", "fuente_estado": "Confirmado"}),
    ("/personas", {"nombre": "Ana", "rol": "JEFA", "vinculo": "OTRO"}),
    ("/personas", {"nombre": "Ana", "rol": "CORTE", "vinculo": "OTRO", "codigo": "PER-0099"}),
    ("/personas", {"nombre": "", "rol": "CORTE", "vinculo": "OTRO"}),
    ("/colores", {"nombre": "Rojo", "codigo": "COL-0099"}),
    ("/colores", {"nombre": ""}),
    ("/categorias", {"nombre": "Sombreros", "codigo": "CAT-0099"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "-1"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "0.1234567"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "MAGIA",
                  "cuero_m2_por_unidad": "1"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "1", "validado": True}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "1", "codigo": "MOD-9999"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "1", "tamano": "ENORME"}),
    ("/modelos", {"nombre_del_modelo": "Nuevo", "categoria": "Billeteras", "origen_de_los_consumos": "EXCEL",
                  "cuero_m2_por_unidad": "1", "herrajes_usd_por_unidad": "-0.0001"}),
    ("/modelos/MOD-0001/validado", {"validado": "quizás"}),
    ("/modelos/MOD-0001/validado", {"validado": True, "nombre_del_modelo": "x"}),
    ("/modelos/MOD-0001/consumos", {"cuero_m2_por_unidad": "1", "origen_de_los_consumos": "EXCEL", "validado": True}),
    ("/modelos/MOD-0001/consumos", {"cuero_m2_por_unidad": "1", "origen_de_los_consumos": "EXCEL", "nombre_del_modelo": "x"}),
])
def test_bad_or_calculated_bodies_are_refused_before_the_service(monkeypatch, path, cuerpo):
    client, _ = con_usuario("admin")
    for nombre in ("cambiar_parametro", "crear_persona", "crear_color", "crear_categoria", "crear_modelo",
                   "cambiar_validado", "cambiar_consumos"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post(path, json=cuerpo).status_code == 422


def test_the_changing_user_reaches_the_parameter_service(monkeypatch):
    client, _ = con_usuario("admin")
    visto = {}

    def cambiar(session, codigo, **datos):
        visto.update(codigo=codigo, **datos)
        return {"codigo": codigo, "constante": "x", "valor": D("0.05"), "valor_texto": None, "unidad": "%",
                "que_es": None, "fuente_estado": "Confirmado"}
    monkeypatch.setattr(servicios, "cambiar_parametro", cambiar)
    respuesta = client.post("/parametros/ARREGLOS_PCT", json={"valor": "0.05", "fuente_estado": "Confirmado"})
    assert respuesta.status_code == 200 and respuesta.json()["valor"] == "0.05"
    assert visto["quien"] == "usuario-de-prueba" and visto["estado"] == "Confirmado" and visto["valor"] == D("0.05")


# --- Flows against PostgreSQL --------------------------------------------------------------------------------

from test_api_integration import TOTAL_DOLAR_1700, api, dolar_nuevo, producto  # noqa: E402,F401  (fixture and helpers)


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="admin-de-prueba", email="a@x.com", role=role))


def parametros(api):
    return {p["codigo"]: p for p in api.get("/parametros").json()}


def modelo_cuerpo(**cambios):
    return {
        "nombre_del_modelo": "Billetera de prueba", "categoria": "Billeteras", "tamano": "CHICO",
        "cuero_m2_por_unidad": "0.12", "forro": "MAT-FO02", "forro_m2_por_unidad": "0.1",
        "flex_m2_por_unidad": "0", "goma_eva_m2_por_unidad": "0", "herrajes_usd_por_unidad": "1.5",
        "hilo_y_cemento": "1", "confeccion_estimada_ars": "5500", "horas_de_confeccion": "0.75",
        "origen_de_los_consumos": "ESTIMADO", "nota": "Primer prototipo", **cambios,
    }


def consumos_cuerpo(**cambios):
    """Every consumption field must be sent on an edit (null = missing data): a partial body is refused."""
    return {"cuero_m2_por_unidad": "0.5", "forro": "MAT-FO02", "forro_m2_por_unidad": "0.2",
            "flex_m2_por_unidad": "0.45", "goma_eva_m2_por_unidad": "0", "herrajes_usd_por_unidad": "2",
            "hilo_y_cemento": "1", "confeccion_estimada_ars": "12000", "horas_de_confeccion": None,
            "origen_de_los_consumos": "MEDIDO", **cambios}


# Parameters

def test_an_admin_changes_a_parameter_and_the_next_quote_uses_it(api):
    como("admin")
    codigo = producto(api)["codigo"]
    dolar_nuevo(api)
    antes = api.get(f"/productos/{codigo}").json()["costo_hoy"]
    guardada = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "RECOTIZACION", "fecha": "2026-10-01"})
    assert guardada.status_code == 201 and D(antes["arreglos"]) == 0 and D(antes["total_ars"]) == TOTAL_DOLAR_1700

    cambio = api.post("/parametros/ARREGLOS_PCT", json={
        "valor": "0.05", "fuente_estado": "Confirmado", "nota": "Robert 27/10"})
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["valor"] == "0.0500" and cambio.json()["fuente_estado"] == "Confirmado: Robert 27/10"
    assert cambio.json()["valor_texto"] is None and parametros(api)["ARREGLOS_PCT"]["valor"] == "0.0500"

    despues = api.get(f"/productos/{codigo}").json()["costo_hoy"]
    assert D(despues["arreglos"]) == TOTAL_DOLAR_1700 * D("0.05")
    assert D(despues["total_ars"]) == TOTAL_DOLAR_1700 * D("1.05")
    # A saved quote is a snapshot: the new parameter does not touch it.
    assert D(api.get(f"/productos/{codigo}").json()["cotizaciones"][0]["total_ars"]) == TOTAL_DOLAR_1700
    assert D(api.get(f"/productos/{codigo}").json()["cotizaciones"][0]["arreglos"]) == 0


def test_the_tolerances_and_the_iva_flag_are_read_by_the_next_quote_check(api):
    como("admin")
    codigo = producto(api)["codigo"]
    api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    dolar_nuevo(api)
    assert api.get(f"/productos/{codigo}").json()["recotizar"] is True
    for clave in ("TOLERANCIA_DESVIO_PCT", "VARIACION_DOLAR_RECOTIZAR_PCT"):
        assert api.post(f"/parametros/{clave}", json={"valor": "0.5", "fuente_estado": "Propuesta"}).status_code == 200
    assert api.get(f"/productos/{codigo}").json()["recotizar"] is False  # +7.5 % cost and +10 % dollar are under 50 %


def test_the_current_period_is_a_text_parameter_and_drives_fixed_costs(api):
    como("admin")
    cambio = api.post("/parametros/PERIODO_VIGENTE", json={"valor_texto": "2026-11", "fuente_estado": "Confirmado"})
    assert cambio.status_code == 200 and cambio.json()["valor_texto"] == "2026-11" and cambio.json()["valor"] is None
    assert api.get("/costos-fijos").json()["periodo"] == "2026-11"


@pytest.mark.parametrize("codigo, cuerpo", [
    ("ARREGLOS_PCT", {"valor": "1.5"}), ("ARREGLOS_PCT", {"valor": "-0.1"}), ("ARREGLOS_PCT", {"valor_texto": "0.1"}),
    ("ARREGLOS_PCT", {}), ("ARREGLOS_PCT", {"valor": "0.1", "valor_texto": "x"}),
    ("DOLAR_PARIDAD", {"valor": "0"}), ("DOLAR_PARIDAD", {"valor": "-1"}),
    ("UMBRAL_RETAZO_M2", {"valor": "0"}),
    ("PERIODO_VIGENTE", {"valor_texto": "2026-13"}), ("PERIODO_VIGENTE", {"valor_texto": "octubre"}),
    ("PERIODO_VIGENTE", {"valor": "202610"}), ("PERIODO_VIGENTE", {}),
    ("DOLAR_VIGENTE", {"valor": "1700"}), ("FECHA_DOLAR_VIGENTE", {"valor_texto": "2026-10-01"}),
])
def test_invalid_parameter_changes_are_refused_and_store_nothing(api, codigo, cuerpo):
    como("admin")
    antes = parametros(api)
    respuesta = api.post(f"/parametros/{codigo}", json={**cuerpo, "fuente_estado": "Confirmado"})
    assert respuesta.status_code == 422, respuesta.text
    assert parametros(api) == antes


def test_parameter_edge_values_and_unknown_codes(api):
    como("admin")
    assert api.post("/parametros/NO_EXISTE", json={"valor": "1", "fuente_estado": "Confirmado"}).status_code == 404
    for borde in ("0", "1", "0.0001"):
        assert api.post("/parametros/ARREGLOS_PCT", json={"valor": borde, "fuente_estado": "Pendiente"}).status_code == 200
    ok = api.post("/parametros/ARREGLOS_PCT", json={"valor": "0.05", "fuente_estado": "Pendiente", "nota": "esperando a Robert"})
    assert ok.json()["fuente_estado"] == "Pendiente: esperando a Robert"
    assert servicios.estado_de_parametro(ok.json()["fuente_estado"])[0] == "media"  # the quality report still sees it open
    grupo = {g["clave"]: g for g in api.get("/calidad").json()["grupos"]}["parametros"]
    assert any(h["entidad"] == "ARREGLOS_PCT" for h in grupo["hallazgos"])


def test_a_confirmed_parameter_leaves_the_quality_report(api):
    como("admin")
    antes = {g["clave"]: g for g in api.get("/calidad").json()["grupos"]}["parametros"]["total"]
    api.post("/parametros/TOLERANCIA_DESVIO_PCT", json={"valor": "0.05", "fuente_estado": "Confirmado"})
    despues = {g["clave"]: g for g in api.get("/calidad").json()["grupos"]}["parametros"]
    assert despues["total"] == antes - 1 and all(h["entidad"] != "TOLERANCIA_DESVIO_PCT" for h in despues["hallazgos"])


def test_a_parameter_change_is_logged_with_who_and_values_but_nothing_else(api, caplog):
    como("admin")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        api.post("/parametros/ARREGLOS_PCT", json={"valor": "0.05", "fuente_estado": "Confirmado"})
    linea = " ".join(r.getMessage() for r in caplog.records if "ARREGLOS_PCT" in r.getMessage())
    assert "admin-de-prueba" in linea and "0.0000" in linea and "0.05" in linea


def test_only_an_admin_changes_parameters(api):
    como("cotizador")
    assert api.post("/parametros/ARREGLOS_PCT", json={"valor": "0.05", "fuente_estado": "Confirmado"}).status_code == 403
    como("consulta")
    assert api.post("/parametros/ARREGLOS_PCT", json={"valor": "0.05", "fuente_estado": "Confirmado"}).status_code == 403
    assert parametros(api)["ARREGLOS_PCT"]["valor"] == "0.0000"


# People and taxes

def test_people_are_created_with_a_server_code_and_deactivated_not_deleted(api):
    como("admin")
    nueva = api.post("/personas", json={"nombre": "Lucía", "rol": "VENTAS", "vinculo": "SUELDO_FIJO", "nota": "Vendedora de caja 1"})
    assert nueva.status_code == 201, nueva.text
    assert nueva.json() == {"codigo": "PER-0008", "nombre": "Lucía", "rol": "VENTAS", "activo": True}
    assert api.post("/personas", json={"nombre": " lucía ", "rol": "CORTE", "vinculo": "OTRO"}).status_code == 409
    assert api.post("/personas", json={"nombre": "Otra", "rol": "JEFA", "vinculo": "OTRO"}).status_code == 422
    baja = api.post("/personas/PER-0008/activo", json={"activo": False})
    assert baja.status_code == 200 and baja.json()["activo"] is False
    assert [p["activo"] for p in api.get("/personas").json() if p["codigo"] == "PER-0008"] == [False]
    assert api.post("/personas/PER-0008/activo", json={"activo": True}).json()["activo"] is True
    assert api.post("/personas/PER-9999/activo", json={"activo": False}).status_code == 404
    assert len(api.get("/personas").json()) == 8


def test_people_need_an_admin(api):
    como("cotizador")
    assert api.post("/personas", json={"nombre": "Ana", "rol": "CORTE", "vinculo": "OTRO"}).status_code == 403
    assert api.post("/personas/PER-0001/activo", json={"activo": False}).status_code == 403
    assert len(api.get("/personas").json()) == 7 and api.get("/personas").json()[0]["activo"] is True


def test_taxes_are_listed_with_their_flags_and_cannot_be_edited(api):
    como("consulta")
    impuestos = {i["codigo"]: i for i in api.get("/impuestos").json()}
    assert list(impuestos) == ["IVA", "IIBB", "GANANCIAS"]
    assert impuestos["IVA"]["alicuota"] == "0.210" and impuestos["IVA"]["es_costo_del_producto"] is False
    assert impuestos["IVA"]["base"] == "COMPRA" and impuestos["IIBB"]["alicuota"] is None
    assert set(impuestos["IVA"]) == {"codigo", "nombre", "alicuota", "base", "es_costo_del_producto", "nota"}
    assert api.post("/impuestos", json={}).status_code == 405
    assert api.post("/impuestos/IVA", json={"alicuota": "0"}).status_code in (404, 405)


# Catalogs

def test_colors_get_a_server_code_and_feed_the_product_form(api):
    como("admin")
    assert api.get("/colores").json() == []
    rojo = api.post("/colores", json={"nombre": " Rojo ", "nota": "Pantone 18-1664"})
    assert rojo.status_code == 201 and rojo.json() == {"codigo": "COL-0001", "nombre": "Rojo", "nota": "Pantone 18-1664"}
    assert api.post("/colores", json={"nombre": "Negro"}).json()["codigo"] == "COL-0002"
    assert api.post("/colores", json={"nombre": "rojo"}).status_code == 409
    assert api.post("/colores", json={"nombre": "   "}).status_code == 422
    assert [c["nombre"] for c in api.get("/colores").json()] == ["Negro", "Rojo"]
    assert api.get("/catalogos").json()["colores"] == ["Negro", "Rojo"]
    assert producto(api, color="Rojo")["color"] == "Rojo"


def test_categories_follow_the_seed_code_convention_or_fall_back_to_a_number(api):
    como("admin")
    zapatos = api.post("/categorias", json={"nombre": "Zapatos de vestir"})
    assert zapatos.status_code == 201 and zapatos.json() == {"codigo": "CAT-ZAPA", "nombre": "Zapatos de vestir", "nota": None}
    assert api.post("/categorias", json={"nombre": "Zapatillas"}).json()["codigo"] == "CAT-0001"  # CAT-ZAPA is taken
    assert api.post("/categorias", json={"nombre": "Pi"}).json()["codigo"] == "CAT-0002"  # fewer than four letters
    assert api.post("/categorias", json={"nombre": "billeteras"}).status_code == 409
    assert api.post("/categorias", json={"nombre": "Billeteras"}).status_code == 409
    assert "Zapatos de vestir" in api.get("/catalogos").json()["categorias"]
    codigos = {c["codigo"] for c in api.get("/categorias").json()}
    assert {"CAT-PORT", "CAT-ZAPA", "CAT-0001"} <= codigos and len(codigos) == 19


def test_catalog_writes_need_an_admin(api):
    como("cotizador")
    assert api.post("/colores", json={"nombre": "Rojo"}).status_code == 403
    assert api.post("/categorias", json={"nombre": "Sombreros"}).status_code == 403
    assert api.get("/colores").status_code == 200 and api.get("/categorias").status_code == 200
    assert api.get("/colores").json() == [] and len(api.get("/categorias").json()) == 16


# Models

def test_the_model_list_filters_by_text_category_validation_and_size(api):
    como("admin")
    todos = api.get("/modelos").json()
    assert len(todos) == 325
    assert [m["codigo"] for m in api.get("/modelos", params={"q": "mod-0001"}).json()] == ["MOD-0001"]
    por_texto = api.get("/modelos", params={"q": "portafolio simple"}).json()
    assert por_texto and all("portafolio simple" in m["nombre_del_modelo"].lower() for m in por_texto)
    por_categoria = api.get("/modelos", params={"categoria": "Portafolios"}).json()
    assert por_categoria and all(m["categoria"] == "Portafolios" for m in por_categoria)
    assert api.get("/modelos", params={"validado": "true"}).json() == []
    assert len(api.get("/modelos", params={"validado": "false"}).json()) == 325
    con_porcentaje = api.get("/modelos", params={"q": "%"}).json()  # wildcards are plain text: only names with a literal %
    assert 0 < len(con_porcentaje) < 10 and all("%" in m["nombre_del_modelo"] for m in con_porcentaje)
    assert api.get("/modelos", params={"q": "mod_0001"}).json() == []
    assert api.get("/modelos", params={"tamano": "ENORME"}).status_code == 422
    assert api.post("/modelos/MOD-0001/validado", json={"validado": True}).status_code == 200
    assert [m["codigo"] for m in api.get("/modelos", params={"validado": "true"}).json()] == ["MOD-0001"]
    assert len(api.get("/modelos", params={"validado": "false"}).json()) == 324
    assert len(api.get("/modelos", params={"limit": 5, "offset": 2}).json()) == 5


def test_the_model_detail_shows_consumptions_origin_and_how_many_products_use_it(api):
    como("admin")
    detalle = api.get("/modelos/MOD-0001").json()
    assert detalle["codigo"] == "MOD-0001" and detalle["categoria"] == "Portafolios"
    assert D(detalle["cuero_m2_por_unidad"]) == D("0.25") and detalle["forro"] == "MAT-FO02"
    assert detalle["origen_de_los_consumos"] == "EXCEL" and detalle["validado"] is False
    assert D(detalle["horas_de_confeccion"] or 0) >= 0 and "nota" in detalle and detalle["productos"] == 0
    producto(api)
    assert api.get("/modelos/MOD-0001").json()["productos"] == 1
    assert api.get("/modelos/MOD-9999").status_code == 404


def test_a_new_model_gets_a_server_code_starts_unvalidated_and_keeps_exact_decimals(api):
    como("admin")
    creado = api.post("/modelos", json=modelo_cuerpo())
    assert creado.status_code == 201, creado.text
    m = creado.json()
    assert m["codigo"] == "MOD-0326" and m["validado"] is False and m["productos"] == 0
    assert m["nombre_del_modelo"] == "Billetera de prueba" and m["categoria"] == "Billeteras" and m["tamano"] == "CHICO"
    assert (D(m["cuero_m2_por_unidad"]), D(m["forro_m2_por_unidad"]), D(m["herrajes_usd_por_unidad"])) == (
        D("0.12"), D("0.1"), D("1.5"))
    assert m["forro"] == "MAT-FO02" and D(m["confeccion_estimada_ars"]) == D("5500") and m["origen_de_los_consumos"] == "ESTIMADO"
    assert isinstance(m["cuero_m2_por_unidad"], str) and m["nota"] == "Primer prototipo"
    assert len(api.get("/modelos").json()) == 326
    # It can be used right away: a product of the new model is costed from its consumptions.
    codigo = producto(api, modelo="MOD-0326")["codigo"]
    dolar_nuevo(api)
    assert D(api.get(f"/productos/{codigo}").json()["costo_hoy"]["etapas"]["CUERO"]) == D("0.12") * 24 * 1700


def test_model_creation_rules(api):
    como("cotizador")
    assert api.post("/modelos", json=modelo_cuerpo()).status_code == 201  # the cotizador role may create
    assert api.post("/modelos", json=modelo_cuerpo(nombre_del_modelo="  billetera DE prueba ")).status_code == 409
    assert api.post("/modelos", json=modelo_cuerpo(nombre_del_modelo="Portafolio Simple Ch. (mod. 6)")).status_code == 409
    for cambio in (
        {"categoria": "Inexistente"}, {"forro": "MAT-CU01"}, {"forro": "MAT-NOPE"}, {"forro": None},  # leather is not a lining
        {"forro": None, "forro_m2_por_unidad": "0.2"}, {"forro_m2_por_unidad": None},
        {"cuero_m2_por_unidad": None},
    ):
        assert api.post("/modelos", json=modelo_cuerpo(nombre_del_modelo="Otro", **cambio)).status_code == 422, cambio
    sin_forro = api.post("/modelos", json=modelo_cuerpo(nombre_del_modelo="Sin forro", forro=None, forro_m2_por_unidad=None))
    assert sin_forro.status_code == 201 and sin_forro.json()["forro"] is None
    assert len(api.get("/modelos").json()) == 327  # only the two accepted ones were stored


def test_marking_a_model_as_validated_is_a_flag_for_admin_and_cotizador(api):
    como("cotizador")
    assert api.post("/modelos/MOD-0002/validado", json={"validado": True}).json()["validado"] is True
    como("admin")
    assert api.post("/modelos/MOD-0002/validado", json={"validado": False}).json()["validado"] is False
    como("consulta")
    assert api.post("/modelos/MOD-0002/validado", json={"validado": True}).status_code == 403
    assert api.get("/modelos/MOD-0002").json()["validado"] is False
    como("admin")
    assert api.post("/modelos/MOD-9999/validado", json={"validado": True}).status_code == 404
    otros = {m["codigo"] for m in api.get("/modelos", params={"validado": "true"}).json()}
    assert otros == set()


def test_editing_consumptions_is_admin_only_resets_validation_and_changes_only_the_next_quote(api):
    como("admin")
    codigo = producto(api)["codigo"]
    dolar_nuevo(api)
    api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "RECOTIZACION", "fecha": "2026-10-01"})
    api.post("/modelos/MOD-0001/validado", json={"validado": True})
    cuerpo = consumos_cuerpo()

    como("cotizador")
    assert api.post("/modelos/MOD-0001/consumos", json=cuerpo).status_code == 403
    assert D(api.get("/modelos/MOD-0001").json()["cuero_m2_por_unidad"]) == D("0.25")

    como("admin")
    editado = api.post("/modelos/MOD-0001/consumos", json=cuerpo)
    assert editado.status_code == 200, editado.text
    assert D(editado.json()["cuero_m2_por_unidad"]) == D("0.5") and editado.json()["origen_de_los_consumos"] == "MEDIDO"
    assert editado.json()["validado"] is False and editado.json()["productos"] == 1
    assert editado.json()["nombre_del_modelo"] == "Portafolio Simple Ch. (mod. 6)"  # the name never changes here
    ficha = api.get(f"/productos/{codigo}").json()
    assert D(ficha["costo_hoy"]["etapas"]["CUERO"]) == D("0.5") * 24 * 1700
    assert D(ficha["cotizaciones"][0]["cuero"]) == D("0.25") * 24 * 1700  # the saved snapshot is untouched
    assert api.post("/modelos/MOD-9999/consumos", json=cuerpo).status_code == 404
    assert api.post("/modelos/MOD-0001/consumos", json={**cuerpo, "cuero_m2_por_unidad": "-1"}).status_code == 422
    assert D(api.get("/modelos/MOD-0001").json()["cuero_m2_por_unidad"]) == D("0.5")


def test_a_partial_consumption_body_is_refused_so_nothing_is_cleared_by_omission(api):
    como("admin")
    assert api.post("/modelos/MOD-0001/consumos", json={"cuero_m2_por_unidad": "0.5", "origen_de_los_consumos": "MEDIDO"}).status_code == 422
    sin_forro = {k: v for k, v in consumos_cuerpo().items() if k != "forro"}
    assert api.post("/modelos/MOD-0001/consumos", json=sin_forro).status_code == 422
    detalle = api.get("/modelos/MOD-0001").json()
    assert detalle["forro"] == "MAT-FO02" and D(detalle["cuero_m2_por_unidad"]) == D("0.25")


def test_editing_consumptions_is_logged_with_the_previous_values(api, caplog):
    como("admin")
    cuerpo = consumos_cuerpo()
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert api.post("/modelos/MOD-0001/consumos", json=cuerpo).status_code == 200
    linea = " ".join(r.getMessage() for r in caplog.records if "MOD-0001" in r.getMessage())
    assert "admin-de-prueba" in linea and "0.250000" in linea and "0.5" in linea


# Quality report links

def test_quality_findings_of_models_and_parameters_point_to_their_admin_screens(api):
    como("consulta")
    grupos = {g["clave"]: g for g in api.get("/calidad").json()["grupos"]}
    assert grupos["modelos_sin_validar"]["hallazgos"] and grupos["parametros"]["hallazgos"]
    assert {h["ruta"] for h in grupos["modelos_sin_validar"]["hallazgos"]} == {"/admin/modelos"}
    assert {h["ruta"] for h in grupos["modelos"]["hallazgos"]} <= {"/admin/modelos"}
    assert {h["ruta"] for h in grupos["parametros"]["hallazgos"]} == {"/admin/parametros"}
