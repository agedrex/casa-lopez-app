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


# --- Cost-volume view: fixed cost per unit and break-even (SUPUESTO: validar) ---

from backend.costeo import costo_por_unidad, punto_de_equilibrio  # noqa: E402


def test_fixed_cost_per_unit_spreads_the_month_over_produced_units():
    r = costo_por_unidad(D("100000"), D("50"), D("2000"))
    assert r.fijo_por_unidad == D("2000")
    assert r.total_por_unidad == D("4000")


def test_cost_per_unit_without_produced_units_has_no_fixed_share():
    r = costo_por_unidad(D("100000"), D("0"), D("2000"))
    assert r.fijo_por_unidad is None
    assert r.total_por_unidad is None


def test_break_even_is_fixed_over_margin_per_unit():
    r = punto_de_equilibrio(D("100000"), D("2000"), D("2500"))
    assert r.margen_por_unidad == D("500")
    assert r.unidades == D("200")
    assert r.motivo is None


def test_break_even_rounds_units_up_to_whole_units():
    r = punto_de_equilibrio(D("1000"), D("10"), D("13"))
    assert r.unidades == D("334")


def test_break_even_needs_a_price_above_variable_cost():
    for price in (D("2000"), D("1500")):
        r = punto_de_equilibrio(D("100000"), D("2000"), price)
        assert r.unidades is None
        assert r.motivo == "PRECIO_NO_CUBRE_COSTO_VARIABLE"


def test_break_even_without_price_gives_no_number():
    r = punto_de_equilibrio(D("100000"), D("2000"), None)
    assert r.unidades is None and r.motivo == "SIN_PRECIO"


# --- Contribution margin per product (CVU) -----------------------------------

def test_contribution_margin_is_price_minus_variable_cost_over_price_and_over_cost():
    from backend.costeo import margen_de_contribucion
    r = margen_de_contribucion(D("125"), D("100"))
    assert r.margen_unidad == D("25")
    assert r.margen_pct == D("20")
    assert r.markup_pct == D("25")
    assert r.veredicto == "SALUDABLE"


def test_price_at_or_below_variable_cost_does_not_cover_it():
    from backend.costeo import margen_de_contribucion
    for precio in ("100", "90"):
        r = margen_de_contribucion(D(precio), D("100"))
        assert r.veredicto == "NO_CUBRE_VARIABLE"
        assert r.margen_unidad == D(precio) - D("100")


def test_low_margin_is_flagged_only_when_a_threshold_is_given():
    from backend.costeo import margen_de_contribucion
    assert margen_de_contribucion(D("125"), D("100")).veredicto == "SALUDABLE"
    assert margen_de_contribucion(D("125"), D("100"), umbral_pct=D("30")).veredicto == "MC_BAJO"
    assert margen_de_contribucion(D("125"), D("100"), umbral_pct=D("20")).veredicto == "SALUDABLE"


def test_percentages_are_none_when_there_is_nothing_to_divide_by():
    from backend.costeo import margen_de_contribucion
    free_input = margen_de_contribucion(D("50"), D("0"))
    assert free_input.markup_pct is None and free_input.margen_pct == D("100")
    no_price = margen_de_contribucion(D("0"), D("0"))
    assert no_price.margen_pct is None and no_price.veredicto == "NO_CUBRE_VARIABLE"


def test_contribution_margin_keeps_full_precision_and_ignores_fixed_costs():
    from backend.costeo import margen_de_contribucion
    # Row 22 variable cost (subtotal 38760.6) at an example price: no rounding, no fixed costs in the verdict.
    r = margen_de_contribucion(D("60000"), D("38760.6"))
    assert r.margen_unidad == D("21239.4")
    assert r.margen_pct == D("35.399")


# --- Break-even with sales mix (CVU) -----------------------------------------------------------------------------

def _mezcla_de_dos():
    from backend.costeo import ProductoEnMezcla
    # A: price 100, variable 60 -> MC 40 x 10 units = 400 on revenue 1000. B: price 200, variable 150 -> MC 50 x 10 = 500 on 2000.
    return [ProductoEnMezcla(D("100"), D("60"), D("10")), ProductoEnMezcla(D("200"), D("150"), D("10"))]


def test_mix_break_even_uses_the_revenue_weighted_contribution_margin():
    from backend.costeo import equilibrio_con_mezcla
    r = equilibrio_con_mezcla(D("600"), _mezcla_de_dos())
    assert r.motivo is None
    assert r.ingresos == D("3000")
    assert r.margen_contribucion == D("900")
    assert r.margen_contribucion_pct == D("30")  # 900 / 3000
    assert r.costos_fijos == D("600")
    assert r.equilibrio_ingresos == D("2000")  # 600 / 0.30
    assert r.equilibrio_unidades == D("14")  # 20 units x 2000 / 3000 = 13.33 -> 14
    assert r.utilidad == D("300")  # 900 - 600
    assert r.margen_seguridad_pct == D("1000") / D("3000") * 100  # (3000 - 2000) / 3000


def test_mix_break_even_keeps_full_precision_and_only_rounds_units_up():
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    r = equilibrio_con_mezcla(D("1000"), [ProductoEnMezcla(D("30"), D("10"), D("3"))])
    assert r.margen_contribucion_pct == D("60") / D("90") * 100  # not rounded
    assert r.equilibrio_ingresos == D("1500")  # 1000 / (60 / 90)
    assert r.equilibrio_unidades == D("50")  # 1000 / MC 20 per unit, exact: no spurious extra unit


def test_fixed_costs_are_global_and_only_the_mix_moves_the_break_even():
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    base = equilibrio_con_mezcla(D("600"), _mezcla_de_dos())
    # Doubling A's units alone: the fixed costs stay 600 (not shared per product) and only the weighted MC % changes.
    mas_de_a = equilibrio_con_mezcla(D("600"), [ProductoEnMezcla(D("100"), D("60"), D("20")), ProductoEnMezcla(D("200"), D("150"), D("10"))])
    assert mas_de_a.costos_fijos == D("600")
    assert mas_de_a.margen_contribucion == D("1300")
    assert mas_de_a.margen_contribucion_pct == D("32.5")  # 1300 / 4000
    assert mas_de_a.equilibrio_ingresos == D("600") * D("4000") / D("1300")
    assert mas_de_a.equilibrio_ingresos != base.equilibrio_ingresos
    # Same mix, scaled up: the weighted MC % and the break-even revenue do not move.
    doble = equilibrio_con_mezcla(D("600"), [ProductoEnMezcla(D("100"), D("60"), D("20")), ProductoEnMezcla(D("200"), D("150"), D("20"))])
    assert doble.margen_contribucion_pct == base.margen_contribucion_pct
    assert doble.equilibrio_ingresos == base.equilibrio_ingresos
    assert doble.equilibrio_unidades == D("14")  # 40 units x 2000 / 6000 = 13.33 -> 14


def test_no_sales_in_the_mix_gives_a_reason_not_a_number():
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    for mezcla in ([], [ProductoEnMezcla(D("100"), D("60"), D("0"))]):
        r = equilibrio_con_mezcla(D("600"), mezcla)
        assert r.motivo == "SIN_VENTAS"
        assert r.ingresos is None and r.margen_contribucion is None and r.costos_fijos is None
        assert r.equilibrio_ingresos is None and r.equilibrio_unidades is None
        assert r.margen_contribucion_pct is None and r.utilidad is None and r.margen_seguridad_pct is None


@pytest.mark.parametrize("mezcla", [
    [("100", "100", "10")],  # MC exactly 0
    [("100", "120", "10")],  # negative
    [("100", "100", "10"), ("200", "250", "10")],  # negative overall
])
def test_a_mix_whose_total_contribution_is_not_positive_gives_a_reason_not_a_number(mezcla):
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    r = equilibrio_con_mezcla(D("600"), [ProductoEnMezcla(D(p), D(v), D(u)) for p, v, u in mezcla])
    assert r.motivo == "MC_NO_POSITIVO"
    assert r.ingresos is None and r.margen_contribucion is None and r.margen_contribucion_pct is None
    assert r.equilibrio_ingresos is None and r.equilibrio_unidades is None
    assert r.utilidad is None and r.margen_seguridad_pct is None


def test_a_losing_product_is_netted_against_a_winning_one_in_the_mix():
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    r = equilibrio_con_mezcla(D("100"), [ProductoEnMezcla(D("100"), D("120"), D("10")), ProductoEnMezcla(D("200"), D("100"), D("10"))])
    assert r.motivo is None
    assert r.margen_contribucion == D("800")  # -200 + 1000


def test_below_break_even_the_profit_and_the_safety_margin_are_negative():
    from backend.costeo import equilibrio_con_mezcla
    r = equilibrio_con_mezcla(D("1500"), _mezcla_de_dos())
    assert r.motivo is None
    assert r.utilidad == D("-600")  # 900 - 1500
    assert r.equilibrio_ingresos == D("5000")  # 1500 / 0.30
    assert r.margen_seguridad_pct == D("-2000") / D("3000") * 100
    assert r.margen_seguridad_pct < 0
    assert r.equilibrio_unidades == D("34")  # 20 units x 5000 / 3000 = 33.33 -> 34


# --- CVU multiproducto: contribution per unit = net price - variable cost - variable selling expense - IIBB ----------
# The guide's example: price 121.000 with IVA -> net 100.000; cost 50.000; other variable expense 5.000; IIBB 3 %.

def test_the_guide_example_leaves_42000_per_unit_when_selling_expense_and_iibb_are_discounted():
    from backend.costeo import margen_de_contribucion
    neto = D("121000") / D("1.21")
    assert neto == D("100000")
    r = margen_de_contribucion(neto, D("50000"), gasto_venta=D("5000"), iibb=D("3000"))
    assert r.margen_unidad == D("42000") and r.margen_pct == D("42") and r.veredicto == "SALUDABLE"


def test_a_selling_expense_or_iibb_can_turn_a_covered_variable_cost_into_a_loss():
    from backend.costeo import margen_de_contribucion
    assert margen_de_contribucion(D("100"), D("90")).veredicto == "SALUDABLE"
    assert margen_de_contribucion(D("100"), D("90"), gasto_venta=D("5"), iibb=D("5")).veredicto == "NO_CUBRE_VARIABLE"


def test_without_selling_expense_or_iibb_the_margin_is_what_it_always_was():
    from backend.costeo import margen_de_contribucion
    base = margen_de_contribucion(D("125"), D("100"), D("30"))
    explicit = margen_de_contribucion(D("125"), D("100"), D("30"), gasto_venta=D("0"), iibb=D("0"))
    assert base == explicit and (base.margen_unidad, base.margen_pct, base.markup_pct) == (D("25"), D("20"), D("25"))


def test_an_amount_over_the_net_price_is_price_times_fraction_in_the_money_scale():
    from backend.costeo import importe_sobre_precio
    assert importe_sobre_precio(D("100000"), D("0.03")) == D("3000")
    assert importe_sobre_precio(D("100"), D("0")) == D("0")
    assert importe_sobre_precio(D("100.5"), D("0.0333")) == D("3.3467")  # 3.34666... rounded half up to 4 decimals


def test_the_mix_discounts_selling_expense_and_iibb_from_every_product_and_defaults_to_none():
    from backend.costeo import ProductoEnMezcla, equilibrio_con_mezcla
    con = equilibrio_con_mezcla(D("100000"), [ProductoEnMezcla(
        D("100000"), D("50000"), D("10"), gasto_venta_por_unidad=D("5000"), iibb_por_unidad=D("3000"))])
    assert con.margen_contribucion == D("420000") and con.margen_contribucion_pct == D("42")
    assert con.equilibrio_ingresos == D("100000") * D("1000000") / D("420000")
    sin = equilibrio_con_mezcla(D("100000"), [ProductoEnMezcla(D("100000"), D("50000"), D("10"))])
    assert sin.margen_contribucion == D("500000")


def test_contribution_per_workshop_hour_needs_known_positive_hours():
    from backend.costeo import margen_por_hora
    assert margen_por_hora(D("42000"), D("3")) == D("14000")
    assert margen_por_hora(D("-100"), D("4")) == D("-25")
    assert margen_por_hora(D("42000"), None) is None
    assert margen_por_hora(D("42000"), D("0")) is None
