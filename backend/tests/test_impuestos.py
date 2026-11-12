"""Taxes on the sale price (spec S3 of odd/tasks/admin-limpieza-y-mejoras.md).

The taxes are an editable grid (name + percentage, activate/deactivate, nothing is deleted) and they go on the sale
price a person designated (`precio_venta`), never on the cost. The costing engine is untouched.
Pure rules and the HTTP gate first (no database), then the flows against the disposable local PostgreSQL
(skipped without TEST_DATABASE_URL, like test_api_integration.py).
"""

import runpy
import sys
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from backend import api as api_module
from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Impuesto

from test_api_integration import TOTAL_DOLAR_1700, api, dolar_nuevo, producto  # noqa: F401  (fixture and helpers)
from test_migrations import RecordedOperations, VERSIONS, load_revision

IVA = {"codigo": "IVA", "nombre": "IVA", "alicuota": D("0.210")}
IIBB = {"codigo": "IMP-0001", "nombre": "Tasa municipal", "alicuota": D("0.035")}

# --- Pure rules ------------------------------------------------------------------------------------------------


def test_each_active_tax_is_a_line_over_the_net_sale_price_and_the_final_price_adds_them():
    r = servicios.armar_precio_con_impuestos(D("50000"), [IVA, IIBB])
    assert r["impuestos"] == [
        {"codigo": "IVA", "nombre": "IVA", "alicuota": D("0.210"), "monto": D("10500")},
        {"codigo": "IMP-0001", "nombre": "Tasa municipal", "alicuota": D("0.035"), "monto": D("1750")},
    ]
    assert r["total_impuestos"] == D("12250") and r["precio_final"] == D("62250")


def test_taxes_do_not_compound_each_one_reads_the_net_price():
    r = servicios.armar_precio_con_impuestos(D("100"), [IVA, IVA | {"codigo": "X", "alicuota": D("0.10")}])
    assert [i["monto"] for i in r["impuestos"]] == [D("21"), D("10")] and r["precio_final"] == D("131")


def test_amounts_are_rounded_to_four_decimals_so_the_lines_add_up_to_the_total():
    r = servicios.armar_precio_con_impuestos(D("100.01"), [IVA | {"alicuota": D("0.215")}])
    assert r["impuestos"][0]["monto"] == D("21.5022")  # 21.50215 half up
    assert r["precio_final"] == D("100.01") + r["total_impuestos"] == D("121.5122")


def test_without_active_taxes_the_final_price_is_the_net_price():
    r = servicios.armar_precio_con_impuestos(D("50000"), [])
    assert r == {"impuestos": [], "total_impuestos": D("0"), "precio_final": D("50000")}


def test_a_tax_without_percentage_adds_no_line():
    sin_porcentaje = {"codigo": "GANANCIAS", "nombre": "Ganancias", "alicuota": None}
    assert servicios.armar_precio_con_impuestos(D("100"), [sin_porcentaje, IVA])["total_impuestos"] == D("21")


@pytest.mark.parametrize("alicuota, fragmento", [
    (None, "porcentaje"), (D("-0.01"), "fracción"), (D("1.5"), "fracción"), (D("21"), "0,21"),
])
def test_a_percentage_outside_zero_and_one_is_refused_in_spanish(alicuota, fragmento):
    with pytest.raises(servicios.DatosInvalidos) as error:
        servicios.validar_alicuota(alicuota)
    assert fragmento in str(error.value)


@pytest.mark.parametrize("alicuota", [D("0"), D("0.21"), D("1")])
def test_a_percentage_between_zero_and_one_is_accepted(alicuota):
    servicios.validar_alicuota(alicuota)


def test_the_orm_has_the_active_flag_not_null_and_true_by_default():
    columna = Impuesto.__table__.c.activo
    assert columna.nullable is False and str(columna.server_default.arg) == "true"


def test_the_real_margin_is_still_computed_on_the_price_without_taxes():
    # SUPUESTO: validar. Taxes are a pass-through to the tax office, so the margin ignores them.
    r = servicios.armar_rentabilidad(codigo="PRD-0001", costo=D("100"), precio_ingresado=None, precio_guardado=D("200"))
    assert r["precio"] == D("200") and r["margen_unidad"] == D("100")


# --- Migration 0012 --------------------------------------------------------------------------------------------


def test_impuesto_activo_revision_adds_a_not_null_flag_defaulting_to_true_and_reverses_it(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0012_impuesto_activo.py"))
    assert revision["revision"] == "0012_impuesto_activo" and revision["down_revision"] == "0011_precio_material_proveedor"
    revision["upgrade"]()
    columna = operations.metadata.tables["costos.impuesto"].c.activo
    assert columna.nullable is False and str(columna.type.compile(dialect=postgresql.dialect())) == "BOOLEAN"
    assert str(columna.server_default.arg) == "true"
    revision["downgrade"]()
    assert operations.dropped_columns == [("costos", "impuesto", "activo")]
    assert "deactivated" in revision["__doc__"]  # the downgrade warns that the deactivations are lost


# --- HTTP gate (no database) ----------------------------------------------------------------------------------

NUEVAS = [("POST", "/impuestos"), ("POST", "/impuestos/{codigo}/alicuota"), ("POST", "/impuestos/{codigo}/activo")]
CUERPOS = {
    "/impuestos": {"nombre": "Tasa municipal", "alicuota": "0.035"},
    "/impuestos/{codigo}/alicuota": {"alicuota": "0.035"},
    "/impuestos/{codigo}/activo": {"activo": False},
}
RUTAS = {(method, route.path) for route in api_module.router.routes if isinstance(route, APIRoute) for method in route.methods}


@pytest.fixture
def sin_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def con_rol(role):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", email="u@x.com", role=role))
    return TestClient(app)


def test_the_tax_write_endpoints_are_declared():
    assert set(NUEVAS) <= RUTAS


@pytest.mark.parametrize("metodo, path", NUEVAS)
def test_the_tax_write_endpoints_are_closed_without_a_session(sin_base, metodo, path):
    with TestClient(app) as client:
        response = client.request(metodo, path.replace("{codigo}", "IVA"), json=CUERPOS[path])
    assert response.status_code == 401 and response.json() == {"detail": "No autenticado."}


@pytest.mark.parametrize("metodo, path", NUEVAS)
@pytest.mark.parametrize("role", ["gerente", "taller", None, "otro", "gerente,taller"])
def test_the_tax_write_endpoints_refuse_every_role_but_admin(sin_base, monkeypatch, metodo, path, role):
    for nombre in ("crear_impuesto", "cambiar_alicuota_impuesto", "cambiar_activo_impuesto"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    assert con_rol(role).request(metodo, path.replace("{codigo}", "IVA"), json=CUERPOS[path]).status_code == 403


@pytest.mark.parametrize("cuerpo", [
    {}, {"nombre": "X"}, {"alicuota": "0.1"}, {"nombre": "", "alicuota": "0.1"}, {"nombre": "X", "alicuota": "abc"},
    {"nombre": "X", "alicuota": "0.1234"}, {"nombre": "X", "alicuota": "0.1", "es_costo_del_producto": True},
    {"nombre": "X", "alicuota": "0.1", "codigo": "IMP-9999"},
])
def test_a_bad_tax_body_is_a_422_and_never_reaches_the_service(sin_base, monkeypatch, cuerpo):
    monkeypatch.setattr(servicios, "crear_impuesto", lambda *a, **k: pytest.fail("the service must not be called"))
    assert con_rol("admin").post("/impuestos", json=cuerpo).status_code == 422


# --- Flows against PostgreSQL ---------------------------------------------------------------------------------


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role=role))


def nuevo(api, nombre="Tasa municipal", alicuota="0.035"):
    respuesta = api.post("/impuestos", json={"nombre": nombre, "alicuota": alicuota})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def precio_de_venta(api, codigo, precio="50000", **extra):
    respuesta = api.post(f"/productos/{codigo}/precio-venta", json={"precio_ars": precio, **extra})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_a_tax_is_created_with_a_server_code_on_the_sale_price_and_active(api):
    creado = nuevo(api)
    assert creado == {
        "codigo": "IMP-0001", "nombre": "Tasa municipal", "alicuota": "0.035", "base": "VENTA",
        "es_costo_del_producto": False, "nota": None, "activo": True,
    }
    assert nuevo(api, "Percepción de obra", "0.01")["codigo"] == "IMP-0002"
    assert [i["codigo"] for i in api.get("/impuestos").json()] == ["IVA", "IIBB", "GANANCIAS", "IMP-0001", "IMP-0002"]


def test_the_listing_keeps_every_existing_field_and_adds_the_active_flag(api):
    impuestos = {i["codigo"]: i for i in api.get("/impuestos").json()}
    assert set(impuestos["IVA"]) == {"codigo", "nombre", "alicuota", "base", "es_costo_del_producto", "nota", "activo"}
    assert impuestos["IVA"]["alicuota"] == "0.210" and impuestos["IVA"]["base"] == "COMPRA"
    assert impuestos["IVA"]["es_costo_del_producto"] is False and impuestos["IIBB"]["alicuota"] is None
    assert all(i["activo"] is True for i in impuestos.values())


def test_a_repeated_name_is_a_conflict_and_a_bad_percentage_stores_nothing(api):
    nuevo(api)
    assert api.post("/impuestos", json={"nombre": " tasa MUNICIPAL ", "alicuota": "0.02"}).status_code == 409
    assert api.post("/impuestos", json={"nombre": "Otro", "alicuota": "21"}).status_code == 422
    assert api.post("/impuestos", json={"nombre": "Otro", "alicuota": "-0.1"}).status_code == 422
    assert api.post("/impuestos", json={"nombre": "   ", "alicuota": "0.1"}).status_code == 422
    assert len(api.get("/impuestos").json()) == 4


def test_the_percentage_is_edited_in_place_and_a_bad_one_changes_nothing(api):
    cambiado = api.post("/impuestos/IVA/alicuota", json={"alicuota": "0.105"})
    assert cambiado.status_code == 200 and cambiado.json()["alicuota"] == "0.105"
    assert api.post("/impuestos/IIBB/alicuota", json={"alicuota": "0.035"}).json()["alicuota"] == "0.035"  # it had none
    assert api.post("/impuestos/IVA/alicuota", json={"alicuota": "2"}).status_code == 422
    assert api.post("/impuestos/IVA/alicuota", json={"alicuota": None}).status_code == 422
    assert api.post("/impuestos/IMP-9999/alicuota", json={"alicuota": "0.1"}).status_code == 404
    assert {i["codigo"]: i["alicuota"] for i in api.get("/impuestos").json()}["IVA"] == "0.105"


def test_a_tax_is_deactivated_not_deleted_and_can_be_activated_again(api):
    nuevo(api)
    baja = api.post("/impuestos/IMP-0001/activo", json={"activo": False})
    assert baja.status_code == 200 and baja.json()["activo"] is False
    assert [i["activo"] for i in api.get("/impuestos").json() if i["codigo"] == "IMP-0001"] == [False]
    assert api.post("/impuestos/IMP-0001/activo", json={"activo": True}).json()["activo"] is True
    assert api.post("/impuestos/IMP-9999/activo", json={"activo": False}).status_code == 404
    assert len(api.get("/impuestos").json()) == 4  # nothing was deleted
    assert api.delete("/impuestos/IMP-0001").status_code in (404, 405)


def test_only_an_admin_edits_the_taxes_and_the_gerente_cannot_read_them(api):
    for role in ("taller", "gerente"):
        como(role)
        assert api.post("/impuestos", json={"nombre": "X", "alicuota": "0.1"}).status_code == 403
        assert api.post("/impuestos/IVA/alicuota", json={"alicuota": "0.1"}).status_code == 403
        assert api.post("/impuestos/IVA/activo", json={"activo": False}).status_code == 403
        assert api.get("/impuestos").status_code == 403
    como("admin")
    assert {i["codigo"]: i["alicuota"] for i in api.get("/impuestos").json()}["IVA"] == "0.210"


def test_a_saved_price_comes_with_the_breakdown_of_the_active_taxes_and_the_final_price(api):
    codigo = producto(api)["codigo"]
    nuevo(api)
    guardado = precio_de_venta(api, codigo)
    assert guardado["precio_ars"] == "50000.0000"  # existing field, untouched
    assert [(i["codigo"], i["alicuota"], D(i["monto"])) for i in guardado["impuestos"]] == [
        ("IVA", "0.210", D("10500")), ("IMP-0001", "0.035", D("1750"))]
    assert D(guardado["total_impuestos"]) == D("12250") and D(guardado["precio_final"]) == D("62250")
    historial = api.get(f"/productos/{codigo}/precio-venta").json()
    assert D(historial[0]["precio_final"]) == D("62250") and historial[0]["precio_ars"] == "50000.0000"
    assert set(historial[0]) >= {"producto", "precio_ars", "vigente_desde", "nota", "creado_por", "creado_en"}


def test_a_deactivated_tax_leaves_the_breakdown_and_the_history_follows_the_active_ones(api):
    codigo = producto(api)["codigo"]
    nuevo(api)
    precio_de_venta(api, codigo, "50000", vigente_desde="2026-09-01")
    precio_de_venta(api, codigo, "60000", vigente_desde="2026-10-01")
    assert api.post("/impuestos/IVA/activo", json={"activo": False}).status_code == 200
    historial = api.get(f"/productos/{codigo}/precio-venta").json()
    assert [(p["precio_ars"], [i["codigo"] for i in p["impuestos"]], D(p["precio_final"])) for p in historial] == [
        ("60000.0000", ["IMP-0001"], D("62100")), ("50000.0000", ["IMP-0001"], D("51750"))]
    assert api.post("/impuestos/IMP-0001/activo", json={"activo": False}).status_code == 200
    sin = api.get(f"/productos/{codigo}/precio-venta").json()[0]
    assert sin["impuestos"] == [] and D(sin["total_impuestos"]) == 0 and D(sin["precio_final"]) == D("60000")


def test_taxes_never_change_the_cost_nor_the_saved_quotes_nor_the_real_margin(api):
    codigo = producto(api)["codigo"]
    dolar_nuevo(api)
    assert api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"}).status_code == 201
    precio_de_venta(api, codigo, "65000")
    antes = api.get(f"/productos/{codigo}").json()
    margen_antes = api.get(f"/productos/{codigo}/rentabilidad").json()
    nuevo(api, "Tasa municipal", "0.035")
    assert api.post("/impuestos/IVA/alicuota", json={"alicuota": "0.5"}).status_code == 200
    assert api.post("/impuestos/IVA/activo", json={"activo": False}).status_code == 200
    despues = api.get(f"/productos/{codigo}").json()
    assert despues["costo_hoy"] == antes["costo_hoy"] and D(despues["costo_hoy"]["total_ars"]) == TOTAL_DOLAR_1700
    assert despues["cotizaciones"] == antes["cotizaciones"] and D(despues["costo_hoy"]["iva_compras"]) == 0
    margen = api.get(f"/productos/{codigo}/rentabilidad").json()
    assert margen == margen_antes and D(margen["precio"]) == D("65000")
    assert D(margen["margen_unidad"]) == D("65000") - TOTAL_DOLAR_1700  # on the price without taxes
    nueva = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "RECOTIZACION", "fecha": "2026-10-01"})
    assert nueva.status_code == 201 and D(nueva.json()["total_ars"]) == TOTAL_DOLAR_1700
