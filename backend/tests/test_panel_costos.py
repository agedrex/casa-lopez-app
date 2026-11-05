"""Cost panel: the pure assembly (no database) and the HTTP gate of GET /panel/costos."""

from datetime import date
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.servicios import FijosDelMes, ItemDatos, LoteDatos, armar_panel_de_costos

HOY = date(2026, 11, 4)
PERIODO = "2026-11"
ANTERIOR = "2026-10"


def lote(codigo, entrega, envio=None, id=1):
    return LoteDatos(id=id, codigo=codigo, donde="TALLER", taller=None, taller_nombre=None, persona=None,
                     persona_nombre=None, envio=envio, entrega=entrega, estado="CERRADO", nota=None)


def item(lote_codigo, producto, cantidad, id=1):
    return ItemDatos(id=id, codigo=f"IT-{id}", lote=lote_codigo, producto=producto, cantidad=D(cantidad),
                     cotizado=None, pagado=None, nota=None)


def fijos(total, pendientes=0, ficticios=False):
    return FijosDelMes(cargados=True, total_fabrica=D(total), pendientes=pendientes, ficticios=ficticios)


def precio(codigo, vigente_desde, variacion=None, vigente=True, material="MAT-CU01", color=None):
    return {"codigo": codigo, "material": material, "color": color, "precio": D("10"), "moneda": "ARS",
            "vigente_desde": vigente_desde, "vigente": vigente, "variacion_pct": variacion, "salto_grande": False}


DOLAR = {"fecha": date(2026, 11, 2), "ars_por_usd": D("1500"), "fuente": "BNA", "tipo": "VENDEDOR", "nota": None}


def panel(*, periodo=PERIODO, precio_simulado=None, lotes=None, items=None, costos=None, fijos_por_mes=None,
          precios=None, dolar=DOLAR):
    """November: 10 units of A (cost 100) and 30 of B (cost 200); fixed costs 4000 -> 100 per unit."""
    if lotes is None:
        lotes = [lote("LOT-1", date(2026, 11, 3))]
        items = [item("LOT-1", "A", "10", 1), item("LOT-1", "B", "30", 2)]
    return armar_panel_de_costos(
        periodo=periodo, precio=precio_simulado, hoy=HOY, lotes=lotes, items=items or [],
        costos={"A": D("100"), "B": D("200")} if costos is None else costos,
        fijos={PERIODO: fijos("4000")} if fijos_por_mes is None else fijos_por_mes,
        precios=precios or [], dolar=dolar,
    )


def codigos(resultado):
    return [a["codigo"] for a in resultado["avisos"]]


def test_units_and_variable_cost_are_weighted_by_quantity():
    actual = panel()["actual"]
    assert actual["unidades"] == D("40")
    assert actual["unidades_sin_costo"] == D("0")
    assert actual["costo_variable_por_unidad"] == D("175")  # (10 * 100 + 30 * 200) / 40


def test_fixed_cost_per_unit_and_total_per_unit():
    actual = panel()["actual"]
    assert actual["fijos_fabrica"] == D("4000")
    assert actual["fijos_cargados"] is True
    assert actual["fijo_por_unidad"] == D("100")
    assert actual["total_por_unidad"] == D("275")


def test_default_period_and_previous_period_are_reported():
    resultado = panel()
    assert resultado["periodo"] == PERIODO and resultado["periodo_anterior"] == ANTERIOR
    assert resultado["actual"]["periodo"] == PERIODO and resultado["anterior"]["periodo"] == ANTERIOR
    assert panel(periodo="2026-01")["periodo_anterior"] == "2025-12"


def test_a_lot_counts_in_the_month_of_its_delivery_else_its_shipping_date():
    lotes = [lote("LOT-1", None, envio=date(2026, 11, 20), id=1), lote("LOT-2", date(2026, 10, 30), id=2),
             lote("LOT-3", None, None, id=3)]
    items = [item("LOT-1", "A", "5", 1), item("LOT-2", "A", "7", 2), item("LOT-3", "A", "100", 3)]
    resultado = panel(lotes=lotes, items=items)
    assert resultado["actual"]["unidades"] == D("5")
    assert resultado["anterior"]["unidades"] == D("7")


def test_products_without_cost_are_left_out_of_the_average_and_counted():
    resultado = panel(costos={"A": D("100"), "B": None})
    assert resultado["actual"]["costo_variable_por_unidad"] == D("100")
    assert resultado["actual"]["unidades_sin_costo"] == D("30")
    assert resultado["actual"]["unidades"] == D("40")
    assert resultado["actual"]["fijo_por_unidad"] == D("100")  # fixed costs are spread over every unit produced
    assert "PRODUCTOS_SIN_COSTO" in codigos(resultado)


def test_a_product_missing_from_the_cost_map_counts_as_without_cost():
    assert panel(costos={"A": D("100")})["actual"]["unidades_sin_costo"] == D("30")


def test_break_even_without_a_price_gives_a_reason_not_a_number():
    equilibrio = panel()["actual"]["equilibrio"]
    assert equilibrio == {"margen_por_unidad": None, "unidades": None, "motivo": "SIN_PRECIO"}


def test_break_even_with_a_price_is_fixed_costs_over_the_margin_rounded_up():
    equilibrio = panel(precio_simulado=D("275"))["actual"]["equilibrio"]  # margin 100 -> 4000 / 100
    assert equilibrio == {"margen_por_unidad": D("100"), "unidades": D("40"), "motivo": None}
    assert panel(precio_simulado=D("260"))["actual"]["equilibrio"]["unidades"] == D("48")  # 4000 / 85 = 47.06


def test_a_price_that_does_not_cover_the_variable_cost_never_yields_a_number():
    for simulado in (D("175"), D("100")):
        equilibrio = panel(precio_simulado=simulado)["actual"]["equilibrio"]
        assert equilibrio["unidades"] is None
        assert equilibrio["motivo"] == "PRECIO_NO_CUBRE_COSTO_VARIABLE"


def test_break_even_is_reported_for_the_previous_period_too():
    lotes = [lote("LOT-1", date(2026, 10, 3))]
    resultado = panel(lotes=lotes, items=[item("LOT-1", "A", "20")], fijos_por_mes={ANTERIOR: fijos("1000")},
                      precio_simulado=D("150"))
    assert resultado["anterior"]["equilibrio"]["unidades"] == D("20")  # 1000 / (150 - 100)
    assert resultado["actual"]["unidades"] == D("0")


def test_the_variation_compares_with_the_previous_period():
    lotes = [lote("LOT-1", date(2026, 11, 3), id=1), lote("LOT-2", date(2026, 10, 3), id=2)]
    items = [item("LOT-1", "B", "10", 1), item("LOT-2", "A", "10", 2)]
    resultado = panel(lotes=lotes, items=items, fijos_por_mes={PERIODO: fijos("1500"), ANTERIOR: fijos("1000")})
    # variable 200 vs 100; fixed 1500 vs 1000; total (200 + 150) vs (100 + 100)
    assert resultado["variacion_pct"] == {
        "costo_variable_por_unidad": D("100.00"), "fijos_fabrica": D("50.00"), "total_por_unidad": D("75.00"),
    }


def test_the_variation_is_none_when_the_previous_period_has_nothing_to_compare():
    resultado = panel()
    assert resultado["variacion_pct"] == {"costo_variable_por_unidad": None, "fijos_fabrica": None, "total_por_unidad": None}


def test_a_period_without_fixed_cost_rows_is_zero_and_flagged_not_loaded():
    resultado = panel(fijos_por_mes={})
    assert resultado["actual"]["fijos_fabrica"] == D("0")
    assert resultado["actual"]["fijos_cargados"] is False
    assert resultado["actual"]["fijo_por_unidad"] == D("0")
    assert resultado["actual"]["equilibrio"]["unidades"] is None
    assert "FIJOS_NO_CARGADOS" in codigos(resultado)


def test_a_month_without_lots_has_no_per_unit_figures():
    resultado = panel(lotes=[], items=[])
    actual = resultado["actual"]
    assert actual["unidades"] == D("0")
    assert actual["costo_variable_por_unidad"] is None
    assert actual["fijo_por_unidad"] is None and actual["total_por_unidad"] is None
    assert actual["equilibrio"]["unidades"] is None
    assert "SIN_UNIDADES" in codigos(resultado)


def test_pending_and_fictitious_fixed_costs_warn_that_the_break_even_is_not_reliable():
    resultado = panel(fijos_por_mes={PERIODO: fijos("4000", pendientes=2, ficticios=True)})
    assert resultado["actual"]["fijos_pendientes"] == 2 and resultado["actual"]["fijos_ficticios"] is True
    assert {"FIJOS_PENDIENTES", "FIJOS_FICTICIOS"} <= set(codigos(resultado))
    ficticios = next(a for a in resultado["avisos"] if a["codigo"] == "FIJOS_FICTICIOS")
    assert "no es confiable" in ficticios["texto"]


def test_a_clean_panel_only_carries_the_volume_notice():
    resultado = panel()
    assert codigos(resultado) == ["VOLUMEN_PRODUCIDO"]
    assert resultado["avisos"][0]["texto"] == "El volumen es lo producido en lotes, no lo vendido."


def test_the_volume_notice_is_always_present():
    assert "VOLUMEN_PRODUCIDO" in codigos(panel(lotes=[], items=[], fijos_por_mes={}, dolar=None))


def test_prices_that_went_up_are_the_five_newest_with_a_positive_variation():
    precios = [precio(f"PRE-{n}", date(2026, 10, n), variacion=D(n)) for n in range(9, 0, -1)]  # newest first
    precios.insert(1, precio("PRE-BAJA", date(2026, 10, 8), variacion=D("-5")))
    precios.insert(2, precio("PRE-NADA", date(2026, 10, 8), variacion=None))
    subieron = panel(precios=precios)["precios_que_subieron"]
    assert [p["variacion_pct"] for p in subieron] == [D(9), D(8), D(7), D(6), D(5)]
    assert set(subieron[0]) == {"material", "color", "precio", "moneda", "vigente_desde", "variacion_pct", "salto_grande"}


def test_stale_prices_are_the_vigente_ones_older_than_ninety_days_oldest_first():
    precios = [
        precio("PRE-1", date(2026, 8, 5)),                      # 91 days: stale
        precio("PRE-2", date(2026, 8, 6)),                      # exactly 90 days: not stale
        precio("PRE-3", date(2025, 1, 1), vigente=False),       # superseded: ignored
        precio("PRE-4", date(2026, 1, 10), material="MAT-FO01", color="Negro"),
    ]
    resultado = panel(precios=precios)
    viejos = resultado["precios_viejos"]
    assert viejos["cantidad"] == 2
    assert viejos["mas_viejos"] == [
        {"material": "MAT-FO01", "color": "Negro", "vigente_desde": date(2026, 1, 10)},
        {"material": "MAT-CU01", "color": None, "vigente_desde": date(2026, 8, 5)},
    ]
    assert "PRECIOS_VIEJOS" in codigos(resultado)


def test_stale_prices_list_at_most_five_but_count_them_all():
    precios = [precio(f"PRE-{n}", date(2026, 1, n)) for n in range(1, 9)]
    viejos = panel(precios=precios)["precios_viejos"]
    assert viejos["cantidad"] == 8 and len(viejos["mas_viejos"]) == 5


def test_the_dollar_is_old_after_seven_days():
    fresco = panel(dolar={**DOLAR, "fecha": date(2026, 10, 28)})  # 7 days
    assert fresco["dolar_viejo"] is False and "DOLAR_VIEJO" not in codigos(fresco)
    viejo = panel(dolar={**DOLAR, "fecha": date(2026, 10, 27)})  # 8 days
    assert viejo["dolar_viejo"] is True and "DOLAR_VIEJO" in codigos(viejo)
    assert viejo["dolar"] == {"fecha": date(2026, 10, 27), "ars_por_usd": D("1500"), "fuente": "BNA"}


def test_without_a_dollar_the_panel_says_so():
    resultado = panel(dolar=None)
    assert resultado["dolar"] is None and resultado["dolar_viejo"] is True
    assert "DOLAR_VIEJO" in codigos(resultado)


# --- Incomplete data never breaks the panel ----------------------------------------------------------------

def test_an_empty_database_still_answers_with_the_warnings():
    resultado = panel(lotes=[], items=[], costos={}, fijos_por_mes={}, dolar=None, precios=[])
    assert resultado["actual"]["unidades"] == D("0")
    assert resultado["actual"]["costo_variable_por_unidad"] is None and resultado["actual"]["total_por_unidad"] is None
    assert resultado["actual"]["fijo_por_unidad"] is None
    assert resultado["actual"]["equilibrio"]["motivo"] == "SIN_PRECIO"
    assert resultado["variacion_pct"] == {"costo_variable_por_unidad": None, "fijos_fabrica": None, "total_por_unidad": None}
    assert codigos(resultado) == ["FIJOS_NO_CARGADOS", "SIN_UNIDADES", "DOLAR_VIEJO", "VOLUMEN_PRODUCIDO"]


@pytest.mark.parametrize("precio_simulado", [None, D("500")])
def test_no_lots_with_fixed_costs_loaded_never_raises(precio_simulado):
    resultado = panel(lotes=[], items=[], precio_simulado=precio_simulado)
    assert resultado["actual"]["fijos_fabrica"] == D("4000") and resultado["actual"]["fijo_por_unidad"] is None
    assert "SIN_UNIDADES" in codigos(resultado) and "FIJOS_NO_CARGADOS" not in codigos(resultado)


@pytest.mark.parametrize("precio_simulado", [None, D("500")])
def test_lots_without_fixed_rows_never_raise_and_say_so(precio_simulado):
    resultado = panel(fijos_por_mes={}, precio_simulado=precio_simulado)
    assert resultado["actual"]["fijos_cargados"] is False and "FIJOS_NO_CARGADOS" in codigos(resultado)
    if precio_simulado is not None:
        assert resultado["actual"]["equilibrio"] == {"margen_por_unidad": None, "unidades": None, "motivo": "SIN_FIJOS"}


@pytest.mark.parametrize("precio_simulado", [None, D("500")])
def test_products_without_cost_never_raise(precio_simulado):
    resultado = panel(costos={}, precio_simulado=precio_simulado)
    actual = resultado["actual"]
    assert actual["unidades_sin_costo"] == D("40") and actual["costo_variable_por_unidad"] is None
    assert actual["total_por_unidad"] is None and actual["fijo_por_unidad"] == D("100")
    assert "PRODUCTOS_SIN_COSTO" in codigos(resultado)
    if precio_simulado is not None:
        assert actual["equilibrio"]["motivo"] == "SIN_COSTO_VARIABLE"


def test_items_of_lots_that_are_not_loaded_or_have_no_date_are_ignored():
    sin_fecha = lote("LOT-X", None, id=2)
    resultado = panel(lotes=[sin_fecha], items=[item("LOT-X", "A", "5", 1), item("LOT-HUERFANO", "A", "5", 2)])
    assert resultado["actual"]["unidades"] == D("0")


def test_a_future_dollar_does_not_break_the_stale_check():
    resultado = panel(dolar={**DOLAR, "fecha": date(2026, 12, 1)})
    assert resultado["dolar_viejo"] is False


# --- HTTP gate ---------------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role="consulta"))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("params", [
    {"periodo": "2026-13"}, {"periodo": "noviembre"}, {"precio": "0"}, {"precio": "-5"}, {"precio": "abc"},
])
def test_invalid_period_or_price_is_a_422_and_never_reaches_the_service(client, monkeypatch, params):
    monkeypatch.setattr(servicios, "panel_de_costos", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.get("/panel/costos", params=params).status_code == 422


def test_a_read_role_can_call_the_panel_and_money_leaves_as_strings(client, monkeypatch):
    llamadas = []

    def falso(session, periodo, precio, hoy=None):
        llamadas.append((periodo, precio))
        return servicios.armar_panel_de_costos(
            periodo=periodo or PERIODO, precio=precio, hoy=HOY, lotes=[lote("LOT-1", date(2026, 11, 3))],
            items=[item("LOT-1", "A", "10")], costos={"A": D("100")}, fijos={PERIODO: fijos("1000")},
            precios=[], dolar=DOLAR)

    monkeypatch.setattr(servicios, "panel_de_costos", falso)
    response = client.get("/panel/costos", params={"periodo": PERIODO, "precio": "250.50"})
    assert response.status_code == 200
    assert llamadas == [(PERIODO, D("250.50"))]
    cuerpo = response.json()
    assert cuerpo["actual"]["costo_variable_por_unidad"] == "100"
    assert cuerpo["actual"]["equilibrio"]["unidades"] == "7"  # 1000 / 150.50 = 6.64 -> 7
    assert cuerpo["dolar"]["ars_por_usd"] == "1500"
    assert cuerpo["avisos"][-1]["codigo"] == "VOLUMEN_PRODUCIDO"


def test_the_price_is_optional(client, monkeypatch):
    llamadas = []
    monkeypatch.setattr(servicios, "panel_de_costos", lambda s, periodo, precio, hoy=None: llamadas.append((periodo, precio)) or panel())
    assert client.get("/panel/costos").status_code == 200
    assert llamadas == [(None, None)]


# --- CVU (cost-volume-profit) block -------------------------------------------------------------------------------
# November: 40 units, variable 175 per unit (7000 in total), fixed 4000.


def test_cvu_without_a_price_is_none():
    assert panel()["actual"]["cvu"] is None


def test_cvu_with_a_price_gives_revenue_contribution_and_profit():
    cvu = panel(precio_simulado=D("275"))["actual"]["cvu"]
    assert cvu["ingresos"] == D("11000")  # 40 x 275
    assert cvu["costo_variable_total"] == D("7000")  # 40 x 175
    assert cvu["margen_contribucion"] == D("4000")  # 11000 - 7000
    assert cvu["margen_contribucion_unidad"] == D("100")
    assert cvu["margen_contribucion_pct"].quantize(D("0.01")) == D("36.36")  # 4000 / 11000
    assert cvu["costos_fijos"] == D("4000")
    assert cvu["utilidad"] == D("0")
    assert cvu["equilibrio_unidades"] == D("40")
    assert cvu["equilibrio_ingresos"] == D("11000")  # 40 x 275
    assert cvu["margen_seguridad_pct"] == D("0")


def test_cvu_profit_and_safety_margin_above_break_even():
    cvu = panel(precio_simulado=D("375"))["actual"]["cvu"]  # margin 200 -> break-even 20 units
    assert cvu["utilidad"] == D("4000")  # 40 x 200 - 4000
    assert cvu["equilibrio_unidades"] == D("20")
    assert cvu["margen_seguridad_pct"] == D("50")  # (40 - 20) / 40


def test_cvu_loss_when_the_price_covers_variable_but_not_fixed_costs():
    cvu = panel(precio_simulado=D("225"))["actual"]["cvu"]  # margin 50 -> 40 x 50 - 4000 = -2000
    assert cvu["utilidad"] == D("-2000")
    assert cvu["equilibrio_unidades"] == D("80")
    assert cvu["margen_seguridad_pct"] == D("-100")  # (40 - 80) / 40


def test_cvu_is_none_when_the_price_does_not_cover_the_variable_cost_or_data_is_missing():
    assert panel(precio_simulado=D("150"))["actual"]["cvu"] is None
    assert panel(precio_simulado=D("275"), fijos_por_mes={})["actual"]["cvu"] is None
    assert panel(precio_simulado=D("275"), costos={})["actual"]["cvu"] is None
    assert panel(precio_simulado=D("275"), lotes=[], items=[])["actual"]["cvu"] is None


# --- Cost structure of the month ----------------------------------------------------------------------------------


def test_month_totals_split_the_cost_into_variable_and_fixed():
    actual = panel()["actual"]  # 10 x 100 + 30 x 200 = 7000 variable, 4000 fixed
    assert actual["costo_variable_total"] == D("7000")
    assert actual["costo_total"] == D("11000")
    assert actual["fijos_pct_del_total"].quantize(D("0.01")) == D("36.36")


def test_month_totals_are_none_when_a_part_is_missing():
    for resultado in (panel(fijos_por_mes={}), panel(costos={}), panel(lotes=[], items=[])):
        actual = resultado["actual"]
        assert actual["costo_total"] is None
        assert actual["fijos_pct_del_total"] is None
