"""A lot's cost is frozen at its creation date, and a lot's consumption (lanzamiento-listo T6, S8 and S10).

Against disposable PostgreSQL; skipped without TEST_DATABASE_URL. Each test runs in a rolled-back transaction.
Seeds used: MAT-CU01 at 24 USD/m2 and a dollar of 1545, both since 2026-09-01.
MOD-0001: cuero 0.25 (CU01), forro 0.2 (FO02), flex 0.45, herrajes USD 2, hilo y cemento 1.
MOD-0002: cuero 0.9 (CU01), forro 0.8 (FO01), flex 0.8, herrajes USD 6, hilo y cemento 1.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.main import app
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)

ENVIO = date(2026, 10, 2)


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-lote-costo", role=role))


def producto(api, modelo="MOD-0001"):
    respuesta = api.post("/productos", json={"modelo": modelo, "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA",
                                            "fecha_de_alta": "2026-09-03"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def lote(api, items, envio="2026-10-02"):
    respuesta = api.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": envio,
        "items": [{"producto": p, "cantidad": c} for p, c in items]})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def dolar(api, fecha, valor):
    assert api.post("/dolar", json={"fecha": fecha, "ars_por_usd": valor}).status_code == 201


def precio_cuero(api, fecha, usd):
    respuesta = api.post("/precios", json={"material": "MAT-CU01", "precio": usd, "moneda": "USD",
                                           "unidad_del_precio": "m2", "vigente_desde": fecha})
    assert respuesta.status_code == 201, respuesta.text


def costo_del_lote(api, codigo):
    return api.get(f"/ordenes/{codigo}").json()["costo_total"]


def costo_en_la_lista(api, codigo):
    return next(o for o in api.get("/ordenes").json() if o["codigo"] == codigo)["costo_total"]


def costo_a_la_fecha(api, codigo_producto, fecha):
    return servicios.cotizar(api.session, codigo_producto, fecha).cotizado.desglose.total_ars


# --- S8: the cost is the one of the lot's date ---------------------------------------------------------

def test_changing_a_price_or_the_dollar_after_the_lot_date_does_not_change_its_cost(api):
    como("admin")
    dolar(api, "2026-10-01", "1600")
    precio_cuero(api, "2026-10-01", "25")
    codigo_producto = producto(api)
    codigo = lote(api, [(codigo_producto, "4")])
    esperado = costo_a_la_fecha(api, codigo_producto, ENVIO) * 4
    assert D(costo_del_lote(api, codigo)) == esperado
    assert D(costo_en_la_lista(api, codigo)) == esperado

    dolar(api, "2026-10-10", "2000")
    precio_cuero(api, "2026-10-10", "40")

    # The product's cost of today did move; the lot's did not (neither in the detail nor in the list).
    assert costo_a_la_fecha(api, codigo_producto, date(2026, 10, 11)) * 4 != esperado
    assert D(costo_del_lote(api, codigo)) == esperado
    assert D(costo_en_la_lista(api, codigo)) == esperado
    renglon = api.get(f"/ordenes/{codigo}").json()["items"][0]
    assert D(renglon["total_linea"]) == esperado and D(renglon["costo_por_unidad"]) == esperado / 4


def test_a_price_dated_after_the_lot_is_never_used_even_if_it_is_the_newest(api):
    como("admin")
    codigo_producto = producto(api)
    codigo = lote(api, [(codigo_producto, "1")], envio="2026-09-05")
    antes = D(costo_del_lote(api, codigo))
    # Seed price of MAT-CU01 is 24 USD since 2026-09-01; this one starts after the lot.
    precio_cuero(api, "2026-10-01", "99")
    assert D(costo_del_lote(api, codigo)) == antes == costo_a_la_fecha(api, codigo_producto, date(2026, 9, 5))


def test_a_lot_without_a_date_keeps_costing_with_todays_prices(api):
    como("admin")
    codigo_producto = producto(api)
    respuesta = api.post("/ordenes", json={"donde_se_hace": "INTERNA", "items": [{"producto": codigo_producto, "cantidad": "1"}]})
    assert respuesta.status_code == 201, respuesta.text
    codigo = respuesta.json()["codigo"]
    antes = D(costo_del_lote(api, codigo))
    precio_cuero(api, date.today().isoformat(), "99")
    assert D(costo_del_lote(api, codigo)) > antes


# --- S10: consumption of a lot --------------------------------------------------------------------------

def lote_de_dos(api):
    a, b = producto(api, "MOD-0001"), producto(api, "MOD-0002")
    return lote(api, [(a, "4"), (b, "2")]), a, b


def test_consumption_by_product_and_total_by_material(api):
    como("admin")
    codigo, a, b = lote_de_dos(api)
    respuesta = api.get(f"/ordenes/{codigo}/consumo")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["lote"] == codigo and datos["sin_consumo"] == []
    assert [p["producto"] for p in datos["productos"]] == [a, b]
    primero = datos["productos"][0]
    assert D(primero["cantidad"]) == 4
    por_material = {i["material"]: i for i in primero["insumos"]}
    assert D(por_material["MAT-CU01"]["por_unidad"]) == D("0.25") and D(por_material["MAT-CU01"]["total"]) == 1
    assert por_material["MAT-CU01"]["unidad"] == "m2" and por_material["MAT-CU01"]["material_nombre"] == "Estándar"
    assert D(por_material["MAT-FO02"]["total"]) == D("0.8") and D(por_material["MAT-FL01"]["total"]) == D("1.8")
    assert D(por_material["MAT-HC01"]["total"]) == 4 and por_material["MAT-HC01"]["unidad"] == "juego"
    # A zero consumption ("no lleva") and a money amount (herrajes are USD) are not listed as quantities.
    assert "MAT-GE01" not in por_material and "MAT-HE00" not in por_material
    totales = {t["material"]: t for t in datos["totales"]}
    assert D(totales["MAT-CU01"]["total"]) == D("2.8")  # 0.25 x 4 + 0.9 x 2, summed across products
    assert totales["MAT-CU01"]["productos"] == [a, b]
    assert D(totales["MAT-FO02"]["total"]) == D("0.8") and totales["MAT-FO02"]["productos"] == [a]
    assert D(totales["MAT-FO01"]["total"]) == D("1.6") and D(totales["MAT-FL01"]["total"]) == D("3.4")
    assert D(totales["MAT-HC01"]["total"]) == 6
    assert [t["material"] for t in datos["totales"]][0] == "MAT-CU01"  # leather first, then lining, flex...
    assert "MAT-HE00" not in totales


def test_the_same_product_in_two_rows_is_added_up_in_the_total(api):
    como("admin")
    a = producto(api)
    codigo = lote(api, [(a, "4"), (a, "1")])
    datos = api.get(f"/ordenes/{codigo}/consumo").json()
    assert len(datos["productos"]) == 2
    assert D({t["material"]: t for t in datos["totales"]}["MAT-CU01"]["total"]) == D("1.25")


def test_taller_reads_the_consumption_without_any_money(api):
    como("taller")
    codigo, _, _ = lote_de_dos_como_admin(api)
    como("taller")
    respuesta = api.get(f"/ordenes/{codigo}/consumo")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert set(datos) == {"lote", "estado", "productos", "totales", "sin_consumo"}
    assert set(datos["productos"][0]) == {"item", "producto", "producto_nombre", "cantidad", "insumos"}
    assert set(datos["productos"][0]["insumos"][0]) == {"material", "material_nombre", "color", "unidad", "por_unidad", "total"}
    assert set(datos["totales"][0]) == {"material", "material_nombre", "color", "unidad", "total", "productos"}


def lote_de_dos_como_admin(api):
    como("admin")
    return lote_de_dos(api)


def test_gerente_cannot_read_the_consumption(api):
    como("admin")
    codigo, _, _ = lote_de_dos(api)
    como("gerente")
    assert api.get(f"/ordenes/{codigo}/consumo").status_code == 403


def test_an_unknown_lot_is_a_404(api):
    como("admin")
    respuesta = api.get("/ordenes/LOT-9999/consumo")
    assert respuesta.status_code == 404 and "LOT-9999" in respuesta.json()["detail"]


def test_the_consumption_does_not_change_when_prices_change(api):
    como("admin")
    codigo, _, _ = lote_de_dos(api)
    antes = api.get(f"/ordenes/{codigo}/consumo").json()
    precio_cuero(api, "2026-10-10", "40")
    assert api.get(f"/ordenes/{codigo}/consumo").json() == antes


@pytest.mark.parametrize("ruta", ["/ordenes", "/ordenes/{codigo}"])
def test_existing_lot_reads_keep_their_shape(api, ruta):
    como("admin")
    codigo, _, _ = lote_de_dos(api)
    respuesta = api.get(ruta.format(codigo=codigo))
    assert respuesta.status_code == 200
    fila = respuesta.json()[0] if isinstance(respuesta.json(), list) else respuesta.json()
    assert {"costo_total", "costo_promedio_por_unidad", "unidades", "productos", "avisos"} <= set(fila)
