"""Rule-level tests for the pure costing engine (plantilla v4.1 rules)."""

from datetime import date
from decimal import Decimal as D

import pytest

from backend.costeo import (
    Linea,
    PrecioVigente,
    Precios,
    ItemLote,
    confeccion_externa,
    costear,
    costo_kit,
    necesita_recotizar,
    precio_a_la_fecha,
)

DOLAR = D("1000")


def linea(etapa, consumo, precio, moneda="ARS", desperdicio="0"):
    return Linea(etapa, D(consumo), D(desperdicio), D(precio), moneda)


def test_material_cost_is_consumo_times_one_plus_desperdicio_times_price():
    r = costear([linea("FLEX", "2", "100", desperdicio="0.5")], DOLAR)
    assert r.etapas["FLEX"] == D("300")


def test_usd_price_is_multiplied_by_dolar_and_ars_price_is_not():
    r = costear([linea("CUERO", "0.25", "24", "USD"), linea("FORRO", "0.2", "4053")], DOLAR)
    assert r.etapas["CUERO"] == D("6000")
    assert r.etapas["FORRO"] == D("810.6")


def test_same_stage_lines_are_added_and_missing_stages_are_zero():
    r = costear([linea("CUERO", "1", "10"), linea("CUERO", "2", "10")], DOLAR)
    assert r.etapas["CUERO"] == D("30")
    assert r.etapas["FORRO"] == D("0")
    assert set(r.etapas) == {
        "CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION"
    }


def test_corte_is_always_zero_because_it_is_a_fixed_salary():
    assert costear([], DOLAR).etapas["CORTE"] == D("0")
    with pytest.raises(ValueError):
        costear([linea("CORTE", "1", "3000")], DOLAR)


def test_confeccion_is_added_to_the_subtotal():
    r = costear([linea("CUERO", "1", "100")], DOLAR, confeccion=D("12000"))
    assert r.etapas["CONFECCION"] == D("12000")
    assert r.subtotal == D("12100")


def test_no_gg_is_applied_total_is_subtotal_without_extras():
    r = costear([linea("CUERO", "1", "100")], DOLAR)
    assert r.total_ars == r.subtotal == D("100")


def test_total_usd_is_total_over_dolar():
    r = costear([linea("CUERO", "1", "500")], DOLAR)
    assert r.total_usd == D("0.5")


def test_arreglos_apply_on_subtotal_plus_kit():
    r = costear([linea("CUERO", "1", "100")], DOLAR, componentes_kit=D("100"), arreglos_pct=D("0.05"))
    assert r.arreglos == D("10")
    assert r.total_ars == D("210")


def test_iva_is_cost_only_when_flag_is_on():
    base = [linea("CUERO", "1", "100")]
    assert costear(base, DOLAR, iva_pct=D("0.21")).iva_compras == D("0")
    r = costear(base, DOLAR, iva_pct=D("0.21"), iva_es_costo=True)
    assert r.iva_compras == D("21")
    assert r.total_ars == D("121")


def test_dolar_change_moves_only_usd_priced_lines():
    lineas = [linea("CUERO", "1", "10", "USD"), linea("FORRO", "1", "500")]
    a, b = costear(lineas, D("1000")), costear(lineas, D("2000"))
    assert (a.etapas["CUERO"], b.etapas["CUERO"]) == (D("10000"), D("20000"))
    assert a.etapas["FORRO"] == b.etapas["FORRO"] == D("500")


def test_money_stays_decimal_without_float_drift():
    r = costear([linea("CUERO", "0.1", "0.1"), linea("FORRO", "0.2", "0.1")], DOLAR)
    assert r.subtotal == D("0.03")
    assert isinstance(r.total_ars, D)


@pytest.mark.parametrize("bad", [
    dict(dolar=D("0")),
    dict(dolar=D("-1")),
])
def test_invalid_dolar_is_rejected(bad):
    with pytest.raises(ValueError):
        costear([], bad["dolar"])


def test_negative_consumo_unknown_stage_and_bad_currency_are_rejected():
    for bad in (linea("CUERO", "-1", "1"), linea("XXX", "1", "1"), linea("CUERO", "1", "1", "EUR")):
        with pytest.raises(ValueError):
            costear([bad], DOLAR)


# --- price at a date -------------------------------------------------------

PRECIOS = Precios([
    PrecioVigente("MAT-CU01", None, D("20"), "USD", date(2026, 9, 1)),
    PrecioVigente("MAT-CU01", None, D("30"), "USD", date(2026, 10, 1)),
    PrecioVigente("MAT-CU01", "Azul", D("40"), "USD", date(2026, 9, 15)),
])


def test_price_uses_the_newest_row_not_after_the_date_and_never_the_future():
    assert precio_a_la_fecha(PRECIOS, "MAT-CU01", None, date(2026, 9, 20)).precio == D("20")
    assert precio_a_la_fecha(PRECIOS, "MAT-CU01", None, date(2026, 10, 5)).precio == D("30")
    assert precio_a_la_fecha(PRECIOS, "MAT-CU01", None, date(2026, 8, 1)) is None


def test_color_price_wins_and_falls_back_to_the_generic_price():
    assert precio_a_la_fecha(PRECIOS, "MAT-CU01", "Azul", date(2026, 10, 5)).precio == D("40")
    assert precio_a_la_fecha(PRECIOS, "MAT-CU01", "Rojo", date(2026, 10, 5)).precio == D("30")


def test_unknown_material_has_no_price():
    assert precio_a_la_fecha(PRECIOS, "MAT-XX", None, date(2026, 10, 5)) is None


# --- confeccion externa ----------------------------------------------------

def item(fecha, cotizado, pagado):
    return ItemLote(fecha, D(cotizado) if cotizado is not None else None, D(pagado) if pagado is not None else None)


def test_externa_uses_paid_price_of_the_newest_lot_averaging_same_date():
    items = [item(date(2026, 9, 1), 100, 90), item(date(2026, 10, 1), 200, 180), item(date(2026, 10, 1), 220, 200)]
    assert confeccion_externa(items, D("5")) == D("190")


def test_externa_falls_back_to_quoted_then_to_the_model_estimate():
    assert confeccion_externa([item(date(2026, 10, 1), 200, None)], D("5")) == D("200")
    assert confeccion_externa([item(date(2026, 10, 1), None, 0)], D("5")) == D("5")
    assert confeccion_externa([], D("5")) == D("5")


def test_externa_ignores_lots_after_the_quotation_date():
    items = [item(date(2026, 9, 1), 100, 90), item(date(2026, 10, 1), 200, 180)]
    assert confeccion_externa(items, D("5"), hasta=date(2026, 9, 15)) == D("90")


# --- kit and recotizacion --------------------------------------------------

def test_kit_cost_is_sum_of_quantity_times_component_total():
    assert costo_kit([(D("2"), D("100")), (D("1"), D("50"))]) == D("250")
    assert costo_kit([]) == D("0")


def test_recotizar_on_cost_deviation_or_dolar_move_beyond_tolerance():
    kw = dict(desvio_tol=D("0.05"), dolar_tol=D("0.10"))
    assert not necesita_recotizar(D("104"), D("100"), D("1000"), D("1000"), **kw)
    assert necesita_recotizar(D("106"), D("100"), D("1000"), D("1000"), **kw)
    assert necesita_recotizar(D("94"), D("100"), D("1000"), D("1000"), **kw)
    assert necesita_recotizar(D("100"), D("100"), D("1000"), D("1150"), **kw)
    assert not necesita_recotizar(D("100"), D("100"), D("1000"), D("1090"), **kw)
