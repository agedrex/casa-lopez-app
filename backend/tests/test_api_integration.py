"""API against the disposable local PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
Seeds used: MOD-0001 (cuero 0.25, forro MAT-FO02 0.2, flex 0.45, herrajes 2 USD, hilo 1), dollar 1545 on
2026-09-01, flex price from 2026-09-03.
"""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

TOTAL_INICIAL = D("20760.6")  # 9270 + 810.6 + 4500 + 3090 + 3090 at dollar 1545
TOTAL_DOLAR_1700 = D("22310.6")  # cuero 10200, forro 810.6, flex 4500, herrajes 3400, hilo 3400


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def producto(api, **cambios):
    cuerpo = {"modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA",
              "fecha_de_alta": "2026-09-03", **cambios}
    respuesta = api.post("/productos", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def dolar_nuevo(api, fecha="2026-10-01", valor="1700"):
    assert api.post("/dolar", json={"fecha": fecha, "ars_por_usd": valor}).status_code == 201


def test_create_product_assigns_the_code_and_calculates_the_rest(api):
    ficha = producto(api)
    assert ficha["codigo"] == "PRD-0001"
    assert ficha["nombre"].startswith("Portafolio Simple Ch.") and ficha["categoria"] == "Portafolios"
    assert {(l["etapa"], l["material"]) for l in ficha["receta"]} == {
        ("CUERO", "MAT-CU01"), ("FORRO", "MAT-FO02"), ("FLEX", "MAT-FL01"), ("HERRAJES", "MAT-HE00"),
        ("HILO_CEMENTO", "MAT-HC01"),
    }
    assert producto(api)["codigo"] == "PRD-0002"


def test_ficha_costs_today_at_the_newest_dollar_and_money_is_text(api):
    codigo = producto(api)["codigo"]
    # Newest dollar on record is 2026-09-01, before the flex price (09-03): the cost is not computable yet.
    ficha = api.get(f"/productos/{codigo}").json()
    assert ficha["costo_hoy"] is None and "Sin precio para MAT-FL01 a esa fecha" in ficha["avisos"]
    dolar_nuevo(api)
    ficha = api.get(f"/productos/{codigo}").json()
    assert isinstance(ficha["costo_hoy"]["total_ars"], str)
    assert D(ficha["costo_hoy"]["total_ars"]) == TOTAL_DOLAR_1700 and ficha["avisos"] == []
    assert D(ficha["costo_hoy"]["etapas"]["CUERO"]) == D("10200")
    listado = {p["codigo"]: p for p in api.get("/productos").json()}
    assert D(listado[codigo]["costo_hoy_ars"]) == TOTAL_DOLAR_1700 and listado[codigo]["costo_hoy_usd"] is not None


def test_initial_quote_is_saved_once_and_never_updated(api):
    codigo = producto(api)["codigo"]
    primera = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    assert primera.status_code == 201
    guardada = primera.json()
    assert guardada["fecha"] == "2026-09-03" and D(guardada["dolar"]) == D("1545")
    assert D(guardada["total_ars"]) == TOTAL_INICIAL and guardada["estado"] == "COMPLETA"
    assert D(guardada["total_usd"]) == (TOTAL_INICIAL / D("1545")).quantize(D("0.0001"))
    segunda = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    assert segunda.status_code == 409
    assert len(api.get(f"/productos/{codigo}").json()["cotizaciones"]) == 1


def test_a_later_quote_is_a_new_row_and_flags_recotizar(api):
    codigo = producto(api)["codigo"]
    api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    assert api.get(f"/productos/{codigo}").json()["recotizar"] is None  # cost today is not computable yet
    dolar_nuevo(api)
    ficha = api.get(f"/productos/{codigo}").json()
    assert ficha["recotizar"] is True  # +7.5 % cost and +10.03 % dollar against 5 % / 10 % tolerances
    nueva = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "RECOTIZACION", "fecha": "2026-10-01"})
    assert nueva.status_code == 201 and D(nueva.json()["total_ars"]) == TOTAL_DOLAR_1700
    ficha = api.get(f"/productos/{codigo}").json()
    assert [c["tipo"] for c in ficha["cotizaciones"]] == ["RECOTIZACION", "INICIAL"]
    assert ficha["recotizar"] is False


def test_incomplete_quote_is_refused_with_its_warnings_and_stores_nothing(api):
    codigo = producto(api, fecha_de_alta="2026-09-01")["codigo"]  # flex price starts on 09-03
    respuesta = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    assert respuesta.status_code == 422
    assert "Sin precio para MAT-FL01 a esa fecha" in respuesta.json()["avisos"]
    assert api.get(f"/productos/{codigo}").json()["cotizaciones"] == []


def test_quote_without_a_date_is_refused(api):
    codigo = producto(api, fecha_de_alta=None)["codigo"]
    respuesta = api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "FINAL"})
    assert respuesta.status_code == 422 and "fecha" in respuesta.json()["detail"]


def test_quote_of_an_unknown_product_is_a_404(api):
    assert api.post("/productos/PRD-9999/cotizaciones", json={"tipo": "INICIAL"}).status_code == 404
    assert api.get("/productos/PRD-9999").status_code == 404


def test_prices_are_append_only_and_the_newest_one_is_flagged(api):
    nuevo = {"material": "MAT-CU01", "precio": "26", "moneda": "USD", "unidad_del_precio": "m2", "vigente_desde": "2026-10-01"}
    creado = api.post("/precios", json=nuevo)
    assert creado.status_code == 201 and creado.json()["codigo"] == "PRE-0012" and creado.json()["vigente"] is True
    assert api.post("/precios", json={**nuevo, "precio": "27"}).status_code == 409
    historia = api.get("/precios", params={"material": "MAT-CU01", "a_fecha": "2026-10-02"}).json()
    assert [(p["precio"], p["vigente"]) for p in historia] == [("26.0000", True), ("24.0000", False)]
    assert [p["vigente"] for p in api.get("/precios", params={"material": "MAT-CU01", "a_fecha": "2026-09-30"}).json()] == [False, True]


def test_a_new_price_changes_later_quotes_but_not_stored_ones(api):
    codigo = producto(api)["codigo"]
    api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL"})
    dolar_nuevo(api)
    api.post("/precios", json={"material": "MAT-CU01", "precio": "26", "moneda": "USD", "unidad_del_precio": "m2",
                               "vigente_desde": "2026-10-01"})
    ficha = api.get(f"/productos/{codigo}").json()
    assert D(ficha["costo_hoy"]["etapas"]["CUERO"]) == D("0.25") * 26 * 1700
    assert D(ficha["cotizaciones"][0]["total_ars"]) == TOTAL_INICIAL


def test_price_with_the_wrong_unit_or_unknown_material_is_refused(api):
    base = {"material": "MAT-CU01", "precio": "26", "moneda": "USD", "unidad_del_precio": "cm", "vigente_desde": "2026-10-01"}
    assert api.post("/precios", json=base).status_code == 422
    assert api.post("/precios", json={**base, "unidad_del_precio": "m2", "material": "MAT-NOPE"}).status_code == 422


def test_dollar_is_append_only(api):
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1710"}).status_code == 409
    fechas = [(d["fecha"], d["ars_por_usd"]) for d in api.get("/dolar").json()]
    assert fechas == [("2026-10-01", "1700.0000"), ("2026-09-01", "1545.0000")]


def test_calculated_fields_are_rejected_and_nothing_is_created(api):
    for campo, valor in (("nombre", "Otro nombre"), ("categoria", "Billeteras"), ("control", "OK"), ("costo", "1")):
        respuesta = api.post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-CU01", campo: valor})
        assert respuesta.status_code == 422, campo
    assert api.get("/productos").json() == []
    codigo = producto(api)["codigo"]
    assert api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL", "total_ars": "1"}).status_code == 422


def test_product_rules(api):
    assert api.post("/productos", json={"cuero": "MAT-CU01"}).status_code == 422  # a non-kit needs a model
    assert api.post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-CU03"}).status_code == 422  # lagarto is not quotable
    assert api.post("/productos", json={"modelo": "MOD-0001", "cuero": "MAT-FO02"}).status_code == 422  # not a leather
    assert api.post("/productos", json={"modelo": "MOD-9999"}).status_code == 422
    assert api.post("/productos", json={"modelo": "MOD-0001", "color": "Inexistente"}).status_code == 422


def test_extra_lines_add_a_second_leather(api):
    codigo = producto(api)["codigo"]
    dolar_nuevo(api)
    ficha = api.post(f"/productos/{codigo}/extras", json={"material": "MAT-CU02", "consumo_neto_por_unidad": "0.1"}).json()
    assert [l["material"] for l in ficha["receta"] if l["etapa"] == "CUERO"] == ["MAT-CU01", "MAT-CU02"]
    assert D(api.get(f"/productos/{codigo}").json()["costo_hoy"]["etapas"]["CUERO"]) == D("10200") + D("0.1") * 80 * 1700
    assert api.post(f"/productos/{codigo}/extras", json={"material": "MAT-CU02", "consumo_neto_por_unidad": "0"}).status_code == 422
    assert api.post("/productos/PRD-9999/extras", json={"material": "MAT-CU02", "consumo_neto_por_unidad": "1"}).status_code == 404


def test_external_sewing_follows_the_newest_lot_price(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    dolar_nuevo(api)
    assert D(api.get(f"/productos/{codigo}").json()["costo_hoy"]["etapas"]["CONFECCION"]) == D("12000")  # model estimate
    orden = api.post("/ordenes", json={
        "donde_se_hace": "EXTERNA", "taller": "TAL-0001", "fecha_de_envio": "2026-09-10", "fecha_de_entrega": "2026-09-20",
        "items": [{"producto": codigo, "cantidad": "10", "taller_precio_cotizado_por_unidad_ars": "12500",
                   "taller_precio_pagado_por_unidad_ars": "11000"}],
    })
    assert orden.status_code == 201 and orden.json()["codigo"] == "LOT-0001" and orden.json()["items"][0]["codigo"] == "LIT-0001"
    assert D(api.get(f"/productos/{codigo}").json()["costo_hoy"]["etapas"]["CONFECCION"]) == D("11000")
    assert api.post("/ordenes", json={"donde_se_hace": "EXTERNA", "items": []}).status_code == 422
    assert api.post("/ordenes", json={"donde_se_hace": "EXTERNA", "items": [{"producto": "PRD-9999", "cantidad": "1"}]}).status_code == 422


def test_kit_sums_its_components_and_rejects_cycles(api):
    base = producto(api)["codigo"]
    dolar_nuevo(api)
    kit = producto(api, modelo=None, cuero=None, es_kit=True, nombre_propio="Kit de prueba")["codigo"]
    assert api.post(f"/productos/{base}/componentes", json={"componente": kit, "cantidad": "1"}).status_code == 422  # not a kit
    assert api.post(f"/productos/{kit}/componentes", json={"componente": kit, "cantidad": "1"}).status_code == 422
    agregado = api.post(f"/productos/{kit}/componentes", json={"componente": base, "cantidad": "2"})
    assert agregado.status_code == 201
    assert api.post(f"/productos/{kit}/componentes", json={"componente": base, "cantidad": "1"}).status_code == 409
    assert D(api.get(f"/productos/{kit}").json()["costo_hoy"]["total_ars"]) == TOTAL_DOLAR_1700 * 2
    guardada = api.post(f"/productos/{kit}/cotizaciones", json={"tipo": "INICIAL", "fecha": "2026-10-01"})
    assert guardada.status_code == 201 and D(guardada.json()["componentes_kit"]) == TOTAL_DOLAR_1700 * 2
    otro = producto(api, modelo=None, cuero=None, es_kit=True)["codigo"]
    assert api.post(f"/productos/{otro}/componentes", json={"componente": kit, "cantidad": "1"}).status_code == 201
    ciclo = api.post(f"/productos/{kit}/componentes", json={"componente": otro, "cantidad": "1"})
    assert ciclo.status_code == 422 and "ciclo" in ciclo.json()["detail"]


def test_catalog_reads(api):
    assert len(api.get("/modelos").json()) == 325
    assert len(api.get("/materiales").json()) == 13
    assert len(api.get("/parametros").json()) == 8
    assert len(api.get("/talleres").json()) == 3
    precios = api.get("/precios", params={"a_fecha": "2026-10-01"}).json()
    assert len(precios) == 11 and all(p["vigente"] for p in precios)
    parametro = {p["codigo"]: p for p in api.get("/parametros").json()}["TOLERANCIA_DESVIO_PCT"]
    assert parametro["valor"] == "0.0500"


def test_fixed_costs_default_to_the_current_period_and_add_up(api):
    mes = api.get("/costos-fijos").json()
    assert mes["periodo"] == "2026-10" and len(mes["gastos"]) == 15
    suma = {"FABRICA": D(0), "TIENDA": D(0)}
    for gasto in mes["gastos"]:
        suma[gasto["fabrica_o_tienda"]] += D(gasto["monto_ars_del_mes"] or 0)
    assert (D(mes["total_fabrica"]), D(mes["total_tienda"])) == (suma["FABRICA"], suma["TIENDA"])
    nuevo = api.post("/costos-fijos", json={"periodo": "2026-11", "concepto": "Alquiler", "fabrica_o_tienda": "TIENDA",
                                            "categoria": "ALQUILER", "monto_ars_del_mes": "1000"})
    assert nuevo.status_code == 201
    assert nuevo.json()["periodo"] == "2026-11" and D(nuevo.json()["total_tienda"]) == D("1000") and nuevo.json()["pendientes"] == 0
    assert api.get("/costos-fijos", params={"periodo": "2030-01"}).json()["gastos"] == []
