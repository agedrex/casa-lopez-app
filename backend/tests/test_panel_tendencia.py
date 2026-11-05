"""Monthly trend of the cost panel: the pure assembly (no database) and the HTTP gate of GET /panel/tendencia."""

from datetime import date
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.servicios import FijosDelMes, ItemDatos, LoteDatos, armar_tendencia_de_costos

HASTA = "2026-11"


def lote(codigo, entrega, id=1):
    return LoteDatos(id=id, codigo=codigo, donde="TALLER", taller=None, taller_nombre=None, persona=None,
                     persona_nombre=None, envio=None, entrega=entrega, estado="CERRADO", nota=None)


def item(lote_codigo, producto, cantidad, id=1):
    return ItemDatos(id=id, codigo=f"IT-{id}", lote=lote_codigo, producto=producto, cantidad=D(cantidad),
                     cotizado=None, pagado=None, nota=None)


def fijos(total, pendientes=0, ficticios=False):
    return FijosDelMes(cargados=True, total_fabrica=D(total), pendientes=pendientes, ficticios=ficticios)


def tendencia(*, hasta=HASTA, meses=3, lotes=None, items=None, costos=None, fijos_por_mes=None):
    """Sep: 10 units at 100 with fixed 1000 (total 200); Oct: 20 units at 100 with fixed 4000 (total 300)."""
    if lotes is None:
        lotes = [lote("LOT-1", date(2026, 9, 5), 1), lote("LOT-2", date(2026, 10, 5), 2)]
        items = [item("LOT-1", "A", "10", 1), item("LOT-2", "A", "20", 2)]
    return armar_tendencia_de_costos(
        hasta=hasta, meses=meses, lotes=lotes, items=items or [],
        costos={"A": D("100")} if costos is None else costos,
        fijos={"2026-09": fijos("1000"), "2026-10": fijos("4000")} if fijos_por_mes is None else fijos_por_mes,
    )


def mes(resultado, periodo):
    return next(m for m in resultado["meses"] if m["periodo"] == periodo)


def test_months_come_oldest_first_and_the_window_ends_at_hasta():
    resultado = tendencia(meses=4)
    assert resultado["hasta"] == HASTA
    assert [m["periodo"] for m in resultado["meses"]] == ["2026-08", "2026-09", "2026-10", "2026-11"]


def test_the_window_crosses_the_year_and_a_single_month_is_valid():
    assert [m["periodo"] for m in tendencia(hasta="2026-02", meses=4, lotes=[], items=[])["meses"]] == [
        "2025-11", "2025-12", "2026-01", "2026-02"]
    assert [m["periodo"] for m in tendencia(meses=1)["meses"]] == [HASTA]


def test_a_full_month_has_every_number_and_nothing_missing():
    octubre = mes(tendencia(), "2026-10")
    assert (octubre["unidades"], octubre["unidades_sin_costo"]) == (D("20"), D("0"))
    assert (octubre["fijos_fabrica"], octubre["fijos_cargados"], octubre["fijos_pendientes"], octubre["fijos_ficticios"]) == (
        D("4000"), True, 0, False)
    assert octubre["costo_variable_por_unidad"] == D("100")
    assert octubre["fijo_por_unidad"] == D("200")  # 4000 / 20
    assert octubre["total_por_unidad"] == D("300")
    assert octubre["incompleto"] == []


def test_variation_compares_each_month_with_the_previous_one_in_the_series():
    resultado = tendencia()
    assert mes(resultado, "2026-09")["variacion_pct_total_por_unidad"] is None  # first of the series
    assert mes(resultado, "2026-09")["total_por_unidad"] == D("200")  # 100 + 1000 / 10
    assert mes(resultado, "2026-10")["variacion_pct_total_por_unidad"] == D("50.00")  # 200 -> 300
    assert mes(resultado, "2026-11")["variacion_pct_total_por_unidad"] is None  # nothing to compare


def test_variation_is_null_when_the_previous_month_has_no_number():
    resultado = tendencia(meses=3, hasta="2026-10")  # Aug empty, Sep, Oct
    assert mes(resultado, "2026-08")["total_por_unidad"] is None
    assert mes(resultado, "2026-09")["variacion_pct_total_por_unidad"] is None
    assert mes(resultado, "2026-10")["variacion_pct_total_por_unidad"] == D("50.00")


def test_a_month_without_fixed_costs_says_so_and_has_no_fixed_nor_total_numbers():
    resultado = tendencia(fijos_por_mes={"2026-10": fijos("4000")})
    septiembre = mes(resultado, "2026-09")
    assert septiembre["incompleto"] == ["SIN_FIJOS"]
    assert septiembre["fijos_cargados"] is False and septiembre["fijos_fabrica"] == D("0")
    assert septiembre["costo_variable_por_unidad"] == D("100")  # what is known stays
    assert septiembre["fijo_por_unidad"] is None and septiembre["total_por_unidad"] is None
    assert mes(resultado, "2026-10")["variacion_pct_total_por_unidad"] is None  # not comparable with an incomplete month


def test_pending_amounts_are_flagged_and_not_comparable():
    resultado = tendencia(fijos_por_mes={"2026-09": fijos("1000", pendientes=2), "2026-10": fijos("4000")})
    assert mes(resultado, "2026-09")["incompleto"] == ["FIJOS_PENDIENTES"]
    assert mes(resultado, "2026-09")["fijos_pendientes"] == 2
    assert mes(resultado, "2026-09")["total_por_unidad"] == D("200")  # still shown, flagged
    assert mes(resultado, "2026-10")["variacion_pct_total_por_unidad"] is None


def test_example_fixed_costs_are_flagged_but_still_compared():
    resultado = tendencia(fijos_por_mes={"2026-09": fijos("1000", ficticios=True), "2026-10": fijos("4000", ficticios=True)})
    assert mes(resultado, "2026-10")["incompleto"] == ["FIJOS_FICTICIOS"]
    assert mes(resultado, "2026-10")["fijos_ficticios"] is True
    assert mes(resultado, "2026-10")["variacion_pct_total_por_unidad"] == D("50.00")


def test_a_month_without_lots_has_no_units_and_no_per_unit_numbers():
    noviembre = mes(tendencia(), "2026-11")
    assert noviembre["unidades"] == D("0") and noviembre["costo_variable_por_unidad"] is None
    assert noviembre["fijo_por_unidad"] is None and noviembre["total_por_unidad"] is None
    assert noviembre["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"]


def test_a_lot_without_a_date_does_not_count_in_any_month():
    sin_fecha = LoteDatos(id=9, codigo="LOT-9", donde="CASA", taller=None, taller_nombre=None, persona=None,
                          persona_nombre=None, envio=None, entrega=None, estado="PLANIFICADA", nota=None)
    resultado = tendencia(lotes=[sin_fecha], items=[item("LOT-9", "A", "50", 1)])
    assert all(m["unidades"] == D("0") for m in resultado["meses"])


def test_products_without_cost_are_counted_flagged_and_leave_the_average():
    resultado = tendencia(
        lotes=[lote("LOT-2", date(2026, 10, 5), 2)],
        items=[item("LOT-2", "A", "10", 1), item("LOT-2", "B", "10", 2)], costos={"A": D("100"), "B": None})
    octubre = mes(resultado, "2026-10")
    assert (octubre["unidades"], octubre["unidades_sin_costo"]) == (D("20"), D("10"))
    assert octubre["costo_variable_por_unidad"] == D("100")
    assert octubre["fijo_por_unidad"] == D("200")  # spread over all the units, with or without a cost
    assert octubre["incompleto"] == ["PRODUCTOS_SIN_COSTO"]


def test_when_no_product_has_a_cost_the_variable_and_total_are_null_not_zero():
    resultado = tendencia(
        lotes=[lote("LOT-2", date(2026, 10, 5), 2)], items=[item("LOT-2", "B", "10", 1)], costos={})
    octubre = mes(resultado, "2026-10")
    assert octubre["costo_variable_por_unidad"] is None and octubre["total_por_unidad"] is None
    assert octubre["fijo_por_unidad"] == D("400")
    assert octubre["incompleto"] == ["PRODUCTOS_SIN_COSTO"]


def test_every_flag_can_show_up_together_in_a_fixed_order():
    resultado = tendencia(
        lotes=[lote("LOT-2", date(2026, 10, 5), 2)], items=[item("LOT-2", "B", "10", 1)], costos={},
        fijos_por_mes={"2026-10": fijos("4000", pendientes=1, ficticios=True)})
    assert mes(resultado, "2026-10")["incompleto"] == ["FIJOS_PENDIENTES", "FIJOS_FICTICIOS", "PRODUCTOS_SIN_COSTO"]
    assert mes(resultado, "2026-11")["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"]


def test_a_month_with_nothing_is_still_listed_and_never_breaks():
    resultado = tendencia(lotes=[], items=[], costos={}, fijos_por_mes={})
    assert len(resultado["meses"]) == 3
    for m in resultado["meses"]:
        assert m["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"]
        assert m["unidades"] == D("0") and m["unidades_sin_costo"] == D("0")
        assert m["fijos_fabrica"] == D("0") and m["fijos_cargados"] is False
        assert m["costo_variable_por_unidad"] is None and m["fijo_por_unidad"] is None and m["total_por_unidad"] is None
        assert m["variacion_pct_total_por_unidad"] is None


def test_the_shape_is_fixed_and_the_note_states_the_limits():
    resultado = tendencia()
    assert set(resultado) == {"hasta", "meses", "nota"}
    assert set(resultado["meses"][0]) == {
        "periodo", "unidades", "unidades_sin_costo", "fijos_fabrica", "fijos_cargados", "fijos_pendientes",
        "fijos_ficticios", "costo_variable_por_unidad", "fijo_por_unidad", "total_por_unidad", "incompleto",
        "variacion_pct_total_por_unidad"}
    assert "producido" in resultado["nota"] and "precios de hoy" in resultado["nota"]


# --- HTTP gate ---------------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role="admin"))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("params", [
    {"hasta": "2026-13"}, {"hasta": "noviembre"}, {"hasta": "2026-1"}, {"meses": "0"}, {"meses": "13"},
    {"meses": "-1"}, {"meses": "abc"}, {"meses": "2.5"},
])
def test_invalid_hasta_or_meses_is_a_422_and_never_reaches_the_service(client, monkeypatch, params):
    monkeypatch.setattr(servicios, "tendencia_de_costos", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.get("/panel/tendencia", params=params).status_code == 422


def test_an_admin_gets_the_trend_with_defaults_and_money_as_strings(client, monkeypatch):
    llamadas = []

    def falso(session, hasta, meses, hoy=None):
        llamadas.append((hasta, meses))
        return servicios.armar_tendencia_de_costos(
            hasta=hasta or HASTA, meses=meses, lotes=[lote("LOT-2", date(2026, 10, 5), 2)],
            items=[item("LOT-2", "A", "20", 1)], costos={"A": D("100")}, fijos={"2026-10": fijos("4000")})

    monkeypatch.setattr(servicios, "tendencia_de_costos", falso)
    respuesta = client.get("/panel/tendencia")
    assert respuesta.status_code == 200
    assert llamadas == [(None, 6)]
    cuerpo = respuesta.json()
    assert [m["periodo"] for m in cuerpo["meses"]][-1] == HASTA and len(cuerpo["meses"]) == 6
    octubre = next(m for m in cuerpo["meses"] if m["periodo"] == "2026-10")
    assert octubre["total_por_unidad"] == "300" and octubre["unidades"] == "20" and octubre["fijos_fabrica"] == "4000"
    assert octubre["incompleto"] == [] and octubre["variacion_pct_total_por_unidad"] is None
    assert client.get("/panel/tendencia", params={"hasta": "2026-10", "meses": "12"}).status_code == 200
    assert llamadas[-1] == ("2026-10", 12)


def test_the_note_and_nulls_travel_in_the_response(client, monkeypatch):
    monkeypatch.setattr(servicios, "tendencia_de_costos", lambda s, hasta, meses, hoy=None: tendencia(meses=2, lotes=[], items=[]))
    cuerpo = client.get("/panel/tendencia", params={"meses": 2}).json()
    assert cuerpo["nota"] == servicios.NOTA_DE_TENDENCIA
    assert cuerpo["meses"][1]["total_por_unidad"] is None and cuerpo["meses"][1]["incompleto"] == ["SIN_FIJOS", "SIN_UNIDADES"]
