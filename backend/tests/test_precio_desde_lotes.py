"""Sale price from the lots already made (QA 2026-11-18, S4 of flujo-modelos-lotes-precio): no database needed here.

The cost basis is the cost per unit of the NEWEST FINISHED lot that made the product; without one it falls back to today's
estimated cost. The margin is over the price (net = cost / (1 - margin)) and the active taxes go on top of the net price.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from backend import servicios

IVA = {"codigo": "IVA", "nombre": "IVA", "alicuota": D("0.21")}
IIBB = {"codigo": "IMP-0001", "nombre": "Ingresos Brutos", "alicuota": D("0.035")}


def lote(codigo, costo, *, fecha=date(2026, 11, 10), estado="LISTA", unidades="10"):
    return {"codigo": codigo, "estado": estado, "fecha": fecha, "unidades": D(unidades),
            "costo_por_unidad": None if costo is None else D(costo)}


def armar(lotes=(), estimado="900", impuestos=(IVA,), margen=None):
    return servicios.armar_precio_desde_lotes(
        codigo="PRD-0001", lotes=list(lotes), costo_estimado=None if estimado is None else D(estimado),
        impuestos=list(impuestos), margen_pct=None if margen is None else D(margen))


def test_the_newest_finished_lot_gives_the_cost_and_every_listed_lot_says_if_it_was_used():
    r = armar([lote("LOT-0003", "1200", fecha=date(2026, 11, 15)), lote("LOT-0002", "1000", fecha=date(2026, 10, 1))])
    assert r["fuente_costo"] == "LOTE" and r["costo_por_unidad"] == D("1200") and r["lote_base"] == "LOT-0003"
    assert [(f["codigo"], f["usado"]) for f in r["lotes"]] == [("LOT-0003", True), ("LOT-0002", False)]
    assert r["lotes"][0]["costo_por_unidad"] == D("1200") and r["lotes"][0]["unidades"] == D("10")
    assert r["avisos"] == []


def test_a_lot_whose_cost_cannot_be_computed_is_skipped_for_the_cost_and_not_listed():
    r = armar([lote("LOT-0003", None), lote("LOT-0002", "1000")])
    assert r["lote_base"] == "LOT-0002" and r["costo_por_unidad"] == D("1000")
    assert [f["codigo"] for f in r["lotes"]] == ["LOT-0002"]


def test_without_a_finished_lot_the_cost_is_todays_estimate_and_it_says_so():
    r = armar([], estimado="900")
    assert r["fuente_costo"] == "ESTIMADO" and r["costo_por_unidad"] == D("900") and r["lote_base"] is None
    assert r["lotes"] == [] and r["avisos"] == [servicios.AVISO_PRECIO_SIN_LOTES]


def test_without_lots_and_without_an_estimate_there_is_no_cost_and_no_price():
    r = armar([], estimado=None, margen="30")
    assert r["fuente_costo"] is None and r["costo_por_unidad"] is None
    assert r["precio_neto"] is None and r["precio_final"] is None
    assert r["avisos"] == [servicios.AVISO_PRECIO_SIN_COSTO]


def test_a_cost_of_zero_is_no_cost():
    r = armar([lote("LOT-0001", "0")], estimado="0", margen="30")
    assert r["fuente_costo"] is None and r["precio_neto"] is None


def test_the_net_price_is_the_cost_over_one_minus_the_margin_rounded_to_cents():
    r = armar([lote("LOT-0001", "1000")], margen="30")
    assert r["margen_pct"] == D("30") and r["precio_neto"] == D("1428.57")  # 1000 / 0.7, not 1000 * 1.3
    assert armar([lote("LOT-0001", "1000")], margen="30.5")["precio_neto"] == D("1438.85")  # 1000 / 0.695
    assert armar([lote("LOT-0001", "1000")], margen="0")["precio_neto"] == D("1000.00")


def test_each_active_tax_goes_on_top_of_the_net_price_and_the_final_price_adds_them():
    r = armar([lote("LOT-0001", "1000")], impuestos=(IVA, IIBB), margen="30")
    neto = D("1428.57")
    assert [(i["codigo"], i["alicuota"], i["monto"]) for i in r["impuestos"]] == [
        ("IVA", D("0.21"), D("299.9997")), ("IMP-0001", D("0.035"), D("50.0000"))]
    assert r["total_impuestos"] == sum(i["monto"] for i in r["impuestos"])
    assert r["precio_neto"] == neto and r["precio_final"] == neto + r["total_impuestos"]
    assert r["sin_impuestos"] is False


def test_without_active_taxes_it_does_not_invent_one_and_says_so():
    r = armar([lote("LOT-0001", "1000")], impuestos=(), margen="30")
    assert r["impuestos"] == [] and r["total_impuestos"] == D("0") and r["sin_impuestos"] is True
    assert r["precio_final"] == r["precio_neto"] == D("1428.57")


def test_without_a_margin_only_the_cost_basis_is_returned():
    r = armar([lote("LOT-0001", "1000")])
    assert r["margen_pct"] is None and r["precio_neto"] is None and r["precio_final"] is None
    assert r["impuestos"] == [] and r["total_impuestos"] is None
    assert r["costo_por_unidad"] == D("1000") and r["sin_impuestos"] is False


def test_only_the_most_recent_lots_are_listed_but_the_cost_still_comes_from_the_newest():
    muchos = [lote(f"LOT-{n:04d}", str(1000 + n)) for n in range(9, 0, -1)]
    r = armar(muchos)
    assert len(r["lotes"]) == servicios.MAX_LOTES_DEL_PRECIO and r["lote_base"] == "LOT-0009"
    assert r["lotes"][0]["usado"] is True and not any(f["usado"] for f in r["lotes"][1:])


@pytest.mark.parametrize("margen", ["-1", "100", "150"])
def test_a_margin_outside_zero_to_less_than_100_is_refused(margen):
    with pytest.raises(servicios.DatosInvalidos):
        armar([lote("LOT-0001", "1000")], margen=margen)


def test_the_amounts_stay_decimal():
    r = armar([lote("LOT-0001", "1000")], margen="30")
    for campo in ("costo_por_unidad", "precio_neto", "total_impuestos", "precio_final"):
        assert isinstance(r[campo], D), campo
