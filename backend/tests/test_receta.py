"""Recipe generation lives in the app (not in the sheet): model + product + extras -> lines -> quote."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from backend.costeo import PrecioVigente, Precios
from backend.receta import (
    Extra,
    ModeloReceta,
    ProductoReceta,
    cotizar_producto,
    dolar_a_la_fecha,
    generar_receta,
)

MODELO = ModeloReceta(
    cuero_m2=D("0.25"), forro_codigo="MAT-FO02", forro_m2=D("0.2"), flex_m2=D("0.45"),
    goma_eva_m2=D("0"), herrajes_usd=D("2"), hilo_cemento=D("1"), confeccion_estimada=D("12000"),
)
PRODUCTO = ProductoReceta(cuero_codigo="MAT-CU01", color=None, quien="INTERNA", es_kit=False)
ETAPAS = {
    "MAT-CU01": "CUERO", "MAT-CU02": "CUERO", "MAT-FO02": "FORRO", "MAT-FL01": "FLEX",
    "MAT-GE01": "GOMA_EVA", "MAT-HE00": "HERRAJES", "MAT-HC01": "HILO_CEMENTO",
}
D0 = date(2026, 9, 1)
PRECIOS = Precios([
    PrecioVigente("MAT-CU01", None, D("24"), "USD", D0),
    PrecioVigente("MAT-CU02", None, D("80"), "USD", D0),
    PrecioVigente("MAT-FO02", None, D("4053"), "ARS", D0),
    PrecioVigente("MAT-FL01", None, D("10000"), "ARS", D0),
    PrecioVigente("MAT-GE01", None, D("5857"), "ARS", D0),
    PrecioVigente("MAT-HE00", None, D("1"), "USD", D0),
    PrecioVigente("MAT-HC01", None, D("2"), "USD", D0),
])
DOLARES = [(date(2026, 9, 1), D("1545")), (date(2026, 10, 1), D("1700"))]


def by_stage(lineas):
    return {(l.etapa, l.material): l.consumo for l in lineas}


def test_recipe_has_one_line_per_thing_the_model_carries_and_none_for_zero():
    r = by_stage(generar_receta(MODELO, PRODUCTO, []).lineas)
    assert r == {
        ("CUERO", "MAT-CU01"): D("0.25"), ("FORRO", "MAT-FO02"): D("0.2"), ("FLEX", "MAT-FL01"): D("0.45"),
        ("HERRAJES", "MAT-HE00"): D("2"), ("HILO_CEMENTO", "MAT-HC01"): D("1"),
    }


def test_extras_add_lines_such_as_a_second_leather():
    extra = Extra(material="MAT-CU02", etapa="CUERO", color=None, consumo=D("0.1"))
    r = generar_receta(MODELO, PRODUCTO, [extra]).lineas
    assert [l.material for l in r if l.etapa == "CUERO"] == ["MAT-CU01", "MAT-CU02"]


def test_missing_leather_and_missing_thread_are_warnings_for_non_kits_only():
    sin = ModeloReceta(None, None, None, None, None, None, D("0"), None)
    avisos = generar_receta(sin, PRODUCTO, []).avisos
    assert "Falta cuero" in avisos and "Falta hilo y cemento" in avisos
    kit = ProductoReceta(None, None, "INTERNA", True)
    assert generar_receta(sin, kit, []).avisos == []


def test_leather_consumption_without_a_leather_material_is_a_warning():
    sin_cuero = ProductoReceta(None, None, "INTERNA", False)
    r = generar_receta(MODELO, sin_cuero, [])
    assert "Falta elegir el cuero" in r.avisos
    assert all(l.etapa != "CUERO" for l in r.lineas)


def test_dolar_is_the_newest_rate_not_after_the_date():
    assert dolar_a_la_fecha(DOLARES, date(2026, 9, 20)) == D("1545")
    assert dolar_a_la_fecha(DOLARES, date(2026, 10, 5)) == D("1700")
    assert dolar_a_la_fecha(DOLARES, date(2026, 8, 1)) is None


def cotizar(fecha, producto=PRODUCTO, extras=(), **kw):
    receta = generar_receta(MODELO, producto, list(extras))
    return cotizar_producto(receta, PRECIOS, ETAPAS, DOLARES, fecha, confeccion=kw.pop("confeccion", D("0")), **kw)


def test_quote_at_a_date_uses_that_dates_dolar_and_prices():
    q = cotizar(date(2026, 9, 1))
    assert q.completa and q.avisos == []
    assert q.desglose.dolar == D("1545")
    assert q.desglose.etapas["CUERO"] == D("0.25") * D("24") * D("1545")
    assert q.desglose.etapas["FORRO"] == D("810.6")
    assert q.desglose.etapas["HERRAJES"] == D("2") * D("1545")


def test_requote_with_a_higher_dolar_moves_only_usd_stages():
    a, b = cotizar(date(2026, 9, 1)).desglose, cotizar(date(2026, 10, 1)).desglose
    assert b.etapas["CUERO"] > a.etapas["CUERO"] and b.etapas["HERRAJES"] > a.etapas["HERRAJES"]
    assert a.etapas["FORRO"] == b.etapas["FORRO"] and a.etapas["FLEX"] == b.etapas["FLEX"]


def test_missing_price_makes_the_quote_incomplete_and_names_the_material():
    q = cotizar(date(2026, 8, 1))
    assert not q.completa
    assert any("MAT-CU01" in a for a in q.avisos)


def test_no_dolar_for_the_date_is_incomplete_instead_of_guessing():
    q = cotizar_producto(generar_receta(MODELO, PRODUCTO, []), PRECIOS, ETAPAS, [], date(2026, 9, 1), confeccion=D("0"))
    assert not q.completa and q.desglose is None


def test_waste_comes_from_the_material_and_defaults_to_the_global_factor():
    q = cotizar(date(2026, 9, 1), desperdicio_por_material={"MAT-CU01": D("0.2")}, desperdicio_default=D("0.1"))
    assert q.desglose.etapas["CUERO"] == D("0.25") * D("1.2") * D("24") * D("1545")
    assert q.desglose.etapas["FORRO"] == D("0.2") * D("1.1") * D("4053")


def test_internal_makes_confeccion_zero_and_external_uses_the_given_price():
    interna = cotizar(date(2026, 9, 1), PRODUCTO, confeccion=D("999"))
    externa = cotizar(date(2026, 9, 1), replace(PRODUCTO, quien="EXTERNA"), confeccion=D("999"))
    assert interna.desglose.etapas["CONFECCION"] == D("0")
    assert externa.desglose.etapas["CONFECCION"] == D("999")


def test_unknown_who_makes_it_is_a_warning_and_incomplete():
    q = cotizar(date(2026, 9, 1), replace(PRODUCTO, quien=None))
    assert not q.completa and "Falta elegir quién lo confecciona" in q.avisos
