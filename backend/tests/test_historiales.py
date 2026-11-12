"""Pure rules of the supplier price history and the workshop payment history (no database).

The HTTP flows against PostgreSQL are in test_historiales_integration.py.
"""

from datetime import date
from decimal import Decimal as D

from backend.proveedores import PrecioDeProveedor, materiales_de_proveedor
from backend.servicios import (
    InfoProducto, ItemDatos, LoteDatos, armar_historial_de_taller, porcentaje_de_barra,
)

# --- Supplier: materials and price history ---------------------------------------------------------------------


def precio(id, material, fecha, valor, moneda="ARS", color=None, nombre=None, iva=False, nota=None):
    return PrecioDeProveedor(
        id=id, codigo=f"PRE-{id:04d}", material_id=sum(map(ord, material)), material=material,
        material_nombre=nombre or f"Material {material[-2:]}", color_id=None if color is None else sum(map(ord, color)),
        color=color, precio=D(valor), moneda=moneda, unidad_del_precio="m2", iva_incluido=iva, vigente_desde=fecha,
        nota_fuente=nota,
    )


def test_prices_are_grouped_by_material_and_color_and_listed_newest_first():
    serie = materiales_de_proveedor([
        precio(1, "MAT-FL01", date(2026, 9, 3), "10000"),
        precio(3, "MAT-FL01", date(2026, 11, 1), "12000"),
        precio(2, "MAT-FL01", date(2026, 10, 1), "11000"),
        precio(4, "MAT-GE01", date(2026, 9, 3), "5857"),
    ])
    assert [s["material"] for s in serie] == ["MAT-FL01", "MAT-GE01"]
    flex = serie[0]
    assert [h["precio"] for h in flex["historial"]] == [D("12000"), D("11000"), D("10000")]
    assert flex["cargas"] == 3 and flex["ultimo_precio"] == D("12000") and flex["ultima_fecha"] == date(2026, 11, 1)


def test_each_price_is_compared_with_the_previous_one_even_if_it_was_loaded_later():
    serie = materiales_de_proveedor([
        precio(5, "MAT-FL01", date(2026, 11, 1), "12000"),
        precio(6, "MAT-FL01", date(2026, 9, 1), "10000"),  # loaded after, but older in time
        precio(7, "MAT-FL01", date(2026, 10, 1), "11000"),
    ])[0]
    cambios = {h["precio"]: h["variacion_pct"] for h in serie["historial"]}
    assert cambios == {D("10000"): None, D("11000"): D("10.00"), D("12000"): D("9.09")}
    assert serie["variacion_ultima_pct"] == D("9.09") and serie["variacion_total_pct"] == D("20.00")


def test_a_big_jump_is_flagged_and_the_variation_is_negative_when_the_price_drops():
    serie = materiales_de_proveedor([
        precio(1, "MAT-FL01", date(2026, 9, 1), "100"),
        precio(2, "MAT-FL01", date(2026, 10, 1), "200"),
        precio(3, "MAT-FL01", date(2026, 11, 1), "150"),
    ])[0]
    por_precio = {h["precio"]: h for h in serie["historial"]}
    assert por_precio[D("200")]["salto_grande"] is True and por_precio[D("200")]["variacion_pct"] == D("100.00")
    assert por_precio[D("150")]["salto_grande"] is False and por_precio[D("150")]["variacion_pct"] == D("-25.00")


def test_a_currency_change_is_not_a_variation():
    serie = materiales_de_proveedor([
        precio(1, "MAT-CU01", date(2026, 9, 1), "24", "USD"),
        precio(2, "MAT-CU01", date(2026, 10, 1), "36000", "ARS"),
        precio(3, "MAT-CU01", date(2026, 11, 1), "26", "USD"),
    ])[0]
    por_id = {h["codigo"]: h for h in serie["historial"]}
    assert por_id["PRE-0002"]["variacion_pct"] is None  # first price in pesos
    assert por_id["PRE-0003"]["variacion_pct"] == D("8.33")  # against the last USD price, not the pesos one
    assert serie["variacion_total_pct"] == D("8.33")  # first and last are both USD
    solo_cambio = materiales_de_proveedor([
        precio(1, "MAT-CU01", date(2026, 9, 1), "24", "USD"), precio(2, "MAT-CU01", date(2026, 10, 1), "36000", "ARS"),
    ])[0]
    assert solo_cambio["variacion_ultima_pct"] is None and solo_cambio["variacion_total_pct"] is None


def test_a_color_is_its_own_series_and_the_plain_one_comes_first():
    series = materiales_de_proveedor([
        precio(1, "MAT-CU01", date(2026, 9, 1), "24", "USD", color="Negro"),
        precio(2, "MAT-CU01", date(2026, 9, 1), "20", "USD"),
        precio(3, "MAT-CU01", date(2026, 10, 1), "22", "USD"),
    ])
    assert [(s["color"], s["cargas"]) for s in series] == [(None, 2), ("Negro", 1)]
    assert series[0]["variacion_ultima_pct"] == D("10.00") and series[1]["variacion_ultima_pct"] is None


def test_materials_are_sorted_by_name_and_a_supplier_without_prices_has_none():
    series = materiales_de_proveedor([
        precio(1, "MAT-ZZ01", date(2026, 9, 1), "1", nombre="Zeta"), precio(2, "MAT-AA01", date(2026, 9, 1), "1", nombre="alfa"),
    ])
    assert [s["material_nombre"] for s in series] == ["alfa", "Zeta"]
    assert materiales_de_proveedor([]) == []


def test_bars_compare_prices_of_the_same_currency_only():
    serie = materiales_de_proveedor([
        precio(1, "MAT-CU01", date(2026, 9, 1), "20", "USD"), precio(2, "MAT-CU01", date(2026, 10, 1), "40", "USD"),
        precio(3, "MAT-CU01", date(2026, 11, 1), "1000", "ARS"),
    ])[0]
    assert {h["codigo"]: h["barra_pct"] for h in serie["historial"]} == {"PRE-0001": 50, "PRE-0002": 100, "PRE-0003": 100}


def test_bar_length_is_a_percentage_of_the_biggest_value_or_nothing():
    assert porcentaje_de_barra(D("50"), D("200")) == 25
    assert porcentaje_de_barra(D("200"), D("200")) == 100
    assert porcentaje_de_barra(None, D("200")) is None and porcentaje_de_barra(D("1"), None) is None
    assert porcentaje_de_barra(D("1"), D("0")) is None


# --- Workshop: lots and payments ---------------------------------------------------------------------------------

def lote(codigo, envio, entrega=None, estado="CERRADA"):
    return LoteDatos(id=int(codigo[-4:]), codigo=codigo, donde="EXTERNA", taller="TAL-0001", taller_nombre="Taller",
                     persona=None, persona_nombre=None, envio=envio, entrega=entrega, estado=estado, nota=None)


def item(id, lote_codigo, producto, cantidad, pagado, cotizado=None):
    return ItemDatos(id=id, codigo=f"LIT-{id:04d}", lote=lote_codigo, producto=producto, cantidad=D(cantidad),
                     cotizado=None if cotizado is None else D(cotizado), pagado=None if pagado is None else D(pagado), nota=None)


INFO = {"PRD-0001": InfoProducto("Cartera", "Carteras", "MEDIANO", None),
        "PRD-0002": InfoProducto("Billetera", "Billeteras", "CHICO", None)}


def test_a_lot_adds_up_units_and_what_was_paid_and_averages_over_the_priced_units():
    historial = armar_historial_de_taller(
        [lote("LOT-0001", date(2026, 10, 1))],
        [item(1, "LOT-0001", "PRD-0001", "10", "1000", "1200"), item(2, "LOT-0001", "PRD-0002", "5", "400", "500")], INFO)
    (fila,) = historial["lotes"]
    assert fila["productos"] == 2 and fila["unidades"] == D("15") and fila["unidades_con_precio_pagado"] == D("15")
    assert fila["total_pagado"] == D("12000") and fila["total_cotizado"] == D("14500")
    assert fila["precio_pagado_promedio"] == D("800.0000") and fila["barra_pct"] == 100


def test_units_without_a_paid_price_count_as_units_but_not_in_the_total_or_the_average():
    historial = armar_historial_de_taller(
        [lote("LOT-0001", date(2026, 10, 1))],
        [item(1, "LOT-0001", "PRD-0001", "10", "1000"), item(2, "LOT-0001", "PRD-0002", "5", None),
         item(3, "LOT-0001", "PRD-0002", "5", "0")], INFO)  # a 0 is "not paid yet"
    (fila,) = historial["lotes"]
    assert fila["unidades"] == D("20") and fila["unidades_con_precio_pagado"] == D("10")
    assert fila["total_pagado"] == D("10000") and fila["precio_pagado_promedio"] == D("1000.0000")


def test_a_lot_nothing_was_paid_for_has_no_average_and_no_bar():
    historial = armar_historial_de_taller(
        [lote("LOT-0001", date(2026, 10, 1))], [item(1, "LOT-0001", "PRD-0001", "10", None, "1200")], INFO)
    (fila,) = historial["lotes"]
    assert fila["total_pagado"] == D("0") and fila["precio_pagado_promedio"] is None and fila["barra_pct"] is None
    assert historial["productos"][0]["ultimo_pagado"] is None and historial["productos"][0]["variacion_total_pct"] is None


def test_the_average_is_rounded_to_four_decimals():
    historial = armar_historial_de_taller(
        [lote("LOT-0001", date(2026, 10, 1))],
        [item(1, "LOT-0001", "PRD-0001", "1", "100"), item(2, "LOT-0001", "PRD-0001", "2", "100")], INFO)
    assert historial["lotes"][0]["precio_pagado_promedio"] == D("100.0000")
    historial = armar_historial_de_taller(
        [lote("LOT-0001", date(2026, 10, 1))],
        [item(1, "LOT-0001", "PRD-0001", "1", "100"), item(2, "LOT-0001", "PRD-0001", "2", "101")], INFO)
    assert historial["lotes"][0]["precio_pagado_promedio"] == D("100.6667")


def test_a_product_price_is_compared_with_the_previous_payment_in_time_order():
    lotes = [lote("LOT-0003", date(2026, 11, 1)), lote("LOT-0002", date(2026, 10, 1)), lote("LOT-0001", date(2026, 9, 1))]
    items = [item(1, "LOT-0001", "PRD-0001", "10", "1000"), item(2, "LOT-0002", "PRD-0001", "20", "1100"),
             item(3, "LOT-0003", "PRD-0001", "30", "1650")]
    (producto,) = armar_historial_de_taller(lotes, items, INFO)["productos"]
    assert [(h["lote"], h["pagado"], h["variacion_pct"]) for h in producto["historial"]] == [
        ("LOT-0003", D("1650"), D("50.00")), ("LOT-0002", D("1100"), D("10.00")), ("LOT-0001", D("1000"), None)]
    assert [h["salto_grande"] for h in producto["historial"]] == [False, False, False]  # 50.00 is not "more than" 50
    assert producto["primer_pagado"] == D("1000") and producto["ultimo_pagado"] == D("1650")
    assert producto["variacion_ultima_pct"] == D("50.00") and producto["variacion_total_pct"] == D("65.00")
    assert producto["lotes"] == 3 and producto["unidades"] == D("60") and producto["ultima_fecha"] == date(2026, 11, 1)
    assert [h["barra_pct"] for h in producto["historial"]] == [100, 67, 61]


def test_the_chain_does_not_depend_on_the_order_the_rows_arrive_in():
    lotes = [lote("LOT-0001", date(2026, 9, 1)), lote("LOT-0002", date(2026, 10, 1))]
    items = [item(9, "LOT-0002", "PRD-0001", "1", "2000"), item(1, "LOT-0001", "PRD-0001", "1", "1000")]
    (producto,) = armar_historial_de_taller(lotes, items, INFO)["productos"]
    assert producto["variacion_ultima_pct"] == D("100.00") and producto["historial"][0]["salto_grande"] is True


def test_unpaid_and_undated_rows_are_listed_but_never_enter_the_variation():
    lotes = [lote("LOT-0003", None), lote("LOT-0002", date(2026, 10, 1)), lote("LOT-0001", date(2026, 9, 1))]
    items = [item(1, "LOT-0001", "PRD-0001", "10", "1000"), item(2, "LOT-0002", "PRD-0001", "10", None, "1300"),
             item(3, "LOT-0003", "PRD-0001", "10", "5000")]
    (producto,) = armar_historial_de_taller(lotes, items, INFO)["productos"]
    assert [h["lote"] for h in producto["historial"]] == ["LOT-0002", "LOT-0001", "LOT-0003"]  # undated last
    assert [h["variacion_pct"] for h in producto["historial"]] == [None, None, None]
    assert producto["ultimo_pagado"] == D("1000") and producto["ultima_fecha"] == date(2026, 10, 1)
    assert producto["historial"][0]["pagado"] is None and producto["historial"][0]["cotizado"] == D("1300")


def test_products_come_with_the_most_recently_given_first_and_the_workshop_without_lots_is_empty():
    lotes = [lote("LOT-0002", date(2026, 10, 1)), lote("LOT-0001", date(2026, 9, 1))]
    items = [item(1, "LOT-0001", "PRD-0001", "1", "100"), item(2, "LOT-0002", "PRD-0002", "1", "50")]
    historial = armar_historial_de_taller(lotes, items, INFO)
    assert [p["producto"] for p in historial["productos"]] == ["PRD-0002", "PRD-0001"]
    assert [l["lote"] for l in historial["lotes"]] == ["LOT-0002", "LOT-0001"]
    assert armar_historial_de_taller([], [], {}) == {"lotes": [], "productos": []}


def test_a_lot_with_no_items_is_listed_with_zeros():
    (fila,) = armar_historial_de_taller([lote("LOT-0001", date(2026, 10, 1))], [], {})["lotes"]
    assert fila["productos"] == 0 and fila["unidades"] == D("0") and fila["total_pagado"] == D("0")
    assert fila["precio_pagado_promedio"] is None
