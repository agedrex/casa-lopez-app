"""Cost panel and monthly trend against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
Seeds used: MOD-0001 (cuero 0.25, forro MAT-FO02 0.2, flex 0.45, herrajes 2 USD, hilo 1), dollar 1545 on 2026-09-01,
flex price from 2026-09-03. With a dollar of 1700 loaded on 2026-10-01 one unit of MOD-0001 costs 22310.6.
"""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import GastoPeriodo, TipoCambio

COSTO_UNITARIO = D("22310.6")  # cuero 10200, forro 810.6, flex 4500, herrajes 3400, hilo 3400 at dollar 1700


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-tendencia", role="admin"))
    try:
        with TestClient(app) as client:
            client.session = session
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def producto(api, **cambios):
    respuesta = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03",
        **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def dolar_nuevo(api, fecha="2026-10-01", valor="1700"):
    assert api.post("/dolar", json={"fecha": fecha, "ars_por_usd": valor}).status_code == 201


def lote(api, fecha, *items, estado="CERRADA"):
    respuesta = api.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": fecha, "fecha_de_entrega": fecha, "estado": estado,
        "items": [{"producto": codigo, "cantidad": cantidad} for codigo, cantidad in items]})
    assert respuesta.status_code == 201, respuesta.text


def gasto(api, periodo, concepto, monto, lado="FABRICA", **cambios):
    respuesta = api.post("/costos-fijos", json={
        "periodo": periodo, "concepto": concepto, "fabrica_o_tienda": lado, "categoria": "OTROS",
        **({} if monto is None else {"monto_ars_del_mes": monto}), **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return next(g for g in respuesta.json()["gastos"] if g["concepto"] == concepto)


def mes(cuerpo, periodo):
    return next(m for m in cuerpo["meses"] if m["periodo"] == periodo)


@pytest.fixture
def escenario(api):
    """Jan: 10 units, fixed 10000. Feb: 20 units, fixed 20000 corrected to 30000. Mar: nothing. A store row is ignored."""
    codigo = producto(api)
    dolar_nuevo(api)
    lote(api, "2027-01-10", (codigo, "6"))
    lote(api, "2027-01-20", (codigo, "4"))
    lote(api, "2027-02-10", (codigo, "20"))
    gasto(api, "2027-01", "Alquiler", "10000")
    gasto(api, "2027-01", "Sueldo mostrador", "99999", lado="TIENDA", categoria="SUELDOS")
    febrero = gasto(api, "2027-02", "Alquiler", "20000")
    assert api.post(f"/costos-fijos/{febrero['codigo']}/corregir", json={"monto_ars_del_mes": "30000"}).status_code == 201
    return codigo


def test_the_trend_reads_lots_fixed_costs_and_corrections_from_the_database(api, escenario):
    respuesta = api.get("/panel/tendencia", params={"hasta": "2027-03", "meses": 3})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["hasta"] == "2027-03" and [m["periodo"] for m in cuerpo["meses"]] == ["2027-01", "2027-02", "2027-03"]
    assert cuerpo["nota"] == servicios.NOTA_DE_TENDENCIA
    enero, febrero, marzo = cuerpo["meses"]
    assert D(enero["unidades"]) == 10 and D(enero["unidades_sin_costo"]) == 0
    assert D(enero["fijos_fabrica"]) == 10000 and enero["fijos_cargados"] is True  # the store row is left out
    assert D(enero["costo_variable_por_unidad"]) == COSTO_UNITARIO
    assert D(enero["fijo_por_unidad"]) == 1000 and D(enero["total_por_unidad"]) == COSTO_UNITARIO + 1000
    assert enero["incompleto"] == [] and enero["variacion_pct_total_por_unidad"] is None
    assert D(febrero["unidades"]) == 20
    assert D(febrero["fijos_fabrica"]) == 30000  # the corrected row counts once (not 20000, not 50000)
    assert D(febrero["fijo_por_unidad"]) == 1500 and D(febrero["total_por_unidad"]) == COSTO_UNITARIO + 1500
    assert febrero["incompleto"] == []
    assert D(febrero["variacion_pct_total_por_unidad"]) == D("2.14")  # 500 / 23310.6
    assert D(marzo["unidades"]) == 0 and marzo["total_por_unidad"] is None and marzo["variacion_pct_total_por_unidad"] is None
    assert marzo["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"]
    assert api.get("/panel/tendencia", params={"hasta": "2027-03", "meses": 3}).json() == cuerpo  # same view when read again


def test_the_trend_costs_each_product_once_for_all_the_months(api, escenario, monkeypatch):
    llamadas = []
    original = servicios._costos_totales_de_hoy
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda session, codigos: llamadas.append(set(codigos)) or original(session, codigos))
    assert api.get("/panel/tendencia", params={"hasta": "2027-03", "meses": 12}).status_code == 200
    assert llamadas == [{escenario}]


def test_the_trend_defaults_to_six_months_ending_this_calendar_month(api):
    cuerpo = api.get("/panel/tendencia").json()
    assert len(cuerpo["meses"]) == 6 and cuerpo["hasta"] == cuerpo["meses"][-1]["periodo"] == servicios.mes_de(servicios.date.today())
    assert api.get("/panel/tendencia", params={"meses": 12}).json()["meses"][0]["periodo"] < cuerpo["meses"][0]["periodo"]


def test_the_trend_flags_pending_example_rows_and_products_without_cost(api):
    codigo = producto(api)
    lote(api, "2027-01-10", (codigo, "10"))  # no dollar yet on record that covers the flex price: no cost
    gasto(api, "2027-01", "Alquiler", "1000", ficticio=True)
    gasto(api, "2027-01", "Luz", None)
    cuerpo = api.get("/panel/tendencia", params={"hasta": "2027-01", "meses": 1}).json()
    enero = cuerpo["meses"][0]
    assert enero["incompleto"] == ["FIJOS_PENDIENTES", "FIJOS_FICTICIOS", "PRODUCTOS_SIN_COSTO"]
    assert enero["fijos_pendientes"] == 1 and enero["fijos_ficticios"] is True
    assert D(enero["unidades_sin_costo"]) == 10 and enero["costo_variable_por_unidad"] is None
    assert D(enero["fijo_por_unidad"]) == 100 and enero["total_por_unidad"] is None


def test_the_panel_reads_lots_and_the_corrected_fixed_costs_from_the_database(api, escenario):
    respuesta = api.get("/panel/costos", params={"periodo": "2027-02", "precio": "30000"})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    actual, anterior = cuerpo["actual"], cuerpo["anterior"]
    assert (cuerpo["periodo"], cuerpo["periodo_anterior"]) == ("2027-02", "2027-01")
    assert D(actual["unidades"]) == 20 and D(anterior["unidades"]) == 10
    assert D(actual["fijos_fabrica"]) == 30000 and D(anterior["fijos_fabrica"]) == 10000
    assert D(actual["costo_variable_por_unidad"]) == COSTO_UNITARIO
    assert D(actual["fijo_por_unidad"]) == 1500 and D(actual["total_por_unidad"]) == COSTO_UNITARIO + 1500
    assert D(anterior["total_por_unidad"]) == COSTO_UNITARIO + 1000
    assert D(cuerpo["variacion_pct"]["fijos_fabrica"]) == 200 and D(cuerpo["variacion_pct"]["total_por_unidad"]) == D("2.14")
    assert D(actual["equilibrio"]["margen_por_unidad"]) == D("30000") - COSTO_UNITARIO
    assert D(actual["equilibrio"]["unidades"]) == 4  # 30000 / 7689.4 = 3.9 -> 4
    assert cuerpo["dolar"]["ars_por_usd"] and cuerpo["avisos"][-1]["codigo"] == "VOLUMEN_PRODUCIDO"
    assert "FIJOS_NO_CARGADOS" not in {a["codigo"] for a in cuerpo["avisos"]}


def test_the_panel_and_the_trend_agree_on_the_shared_months(api, escenario):
    panel = api.get("/panel/costos", params={"periodo": "2027-02"}).json()
    tendencia = api.get("/panel/tendencia", params={"hasta": "2027-02", "meses": 2}).json()
    for bloque, fila in ((panel["anterior"], tendencia["meses"][0]), (panel["actual"], tendencia["meses"][1])):
        for campo in ("periodo", "unidades", "unidades_sin_costo", "fijos_fabrica", "fijo_por_unidad", "total_por_unidad",
                      "costo_variable_por_unidad"):
            assert bloque[campo] == fila[campo], campo


def test_the_panel_survives_a_database_without_dollar_lots_or_fixed_costs(api):
    api.session.execute(delete(GastoPeriodo))
    api.session.execute(delete(TipoCambio))
    api.session.flush()
    producto(api)  # a product that cannot be costed without a dollar
    respuesta = api.get("/panel/costos", params={"periodo": "2027-02", "precio": "100"})
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["dolar"] is None and cuerpo["dolar_viejo"] is True
    assert cuerpo["actual"]["unidades"] == "0" and cuerpo["actual"]["total_por_unidad"] is None
    assert [a["codigo"] for a in cuerpo["avisos"]][:3] == ["FIJOS_NO_CARGADOS", "SIN_UNIDADES", "DOLAR_VIEJO"]
    assert api.get("/panel/costos").status_code == 200
    tendencia = api.get("/panel/tendencia", params={"meses": 12})
    assert tendencia.status_code == 200 and len(tendencia.json()["meses"]) == 12
    assert all(m["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"] for m in tendencia.json()["meses"])


def test_lots_with_products_that_cannot_be_costed_do_not_break_the_panel(api):
    api.session.execute(delete(TipoCambio))
    api.session.flush()
    codigo = producto(api)
    lote(api, "2027-02-10", (codigo, "5"))
    gasto(api, "2027-02", "Alquiler", "500")
    cuerpo = api.get("/panel/costos", params={"periodo": "2027-02", "precio": "100"}).json()
    assert D(cuerpo["actual"]["unidades_sin_costo"]) == 5 and cuerpo["actual"]["costo_variable_por_unidad"] is None
    assert cuerpo["actual"]["equilibrio"]["motivo"] == "SIN_COSTO_VARIABLE"
    assert "PRODUCTOS_SIN_COSTO" in {a["codigo"] for a in cuerpo["avisos"]}


def test_the_endpoints_write_nothing(api, escenario):
    filas = api.session.scalar(select(func.count()).select_from(GastoPeriodo))
    api.get("/panel/tendencia", params={"hasta": "2027-03", "meses": 3})
    api.get("/panel/costos", params={"periodo": "2027-02"})
    assert api.session.scalar(select(func.count()).select_from(GastoPeriodo)) == filas
