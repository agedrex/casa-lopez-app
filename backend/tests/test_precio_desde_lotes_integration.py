"""Price of a product from the lots already made, taxes on top (S4 of flujo-modelos-lotes-precio).

Against disposable PostgreSQL; skipped without TEST_DATABASE_URL. Each test runs in a rolled-back transaction.
Seeds used: MOD-0001 with MAT-CU01 at 24 USD/m2 (cuero 0.25, forro 0.2, flex 0.45, herrajes USD 2, hilo y cemento 1).
"""

from decimal import ROUND_HALF_UP, Decimal as D

from backend.auth import Usuario, get_verifier
from backend.main import app
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-precio", email="a@x.com", role=role))


def un_producto(api):
    como("admin")
    respuesta = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"})
    assert respuesta.status_code == 201, respuesta.text
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    return respuesta.json()["codigo"]


def un_lote(api, codigo, cantidad, *, estado, envio, entrega=None):
    respuesta = api.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": envio, "fecha_de_entrega": entrega, "estado": estado,
        "items": [{"producto": codigo, "cantidad": cantidad}]})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def costo_del_lote(api, lote):
    return D(api.get(f"/ordenes/{lote}").json()["costo_promedio_por_unidad"])


def preview(api, codigo, margen=None):
    respuesta = api.get(f"/productos/{codigo}/precio-desde-lotes", params={} if margen is None else {"margen": margen})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def un_impuesto(api, nombre, alicuota):
    respuesta = api.post("/impuestos", json={"nombre": nombre, "alicuota": alicuota})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def test_without_a_finished_lot_the_cost_is_todays_estimate_and_planned_lots_do_not_count(api):
    codigo = un_producto(api)
    un_lote(api, codigo, "5", estado="PLANIFICADA", envio="2026-10-05")
    estimado = D(next(f for f in api.get("/productos", params={"limit": 500}).json() if f["codigo"] == codigo)["costo_hoy_ars"])
    r = preview(api, codigo)
    assert r["fuente_costo"] == "ESTIMADO" and D(r["costo_por_unidad"]) == estimado
    assert r["lotes"] == [] and r["lote_base"] is None and len(r["avisos"]) == 1


def test_the_newest_finished_lot_sets_the_cost_per_unit_and_the_others_are_listed(api):
    codigo = un_producto(api)
    assert api.post("/dolar", json={"fecha": "2026-10-20", "ars_por_usd": "2000"}).status_code == 201
    viejo = un_lote(api, codigo, "10", estado="CERRADA", envio="2026-10-02", entrega="2026-10-05")
    nuevo = un_lote(api, codigo, "4", estado="LISTA", envio="2026-10-25")
    un_lote(api, codigo, "7", estado="EN_CONFECCION", envio="2026-11-02")  # newest, but not finished: ignored
    r = preview(api, codigo)
    assert r["fuente_costo"] == "LOTE" and r["lote_base"] == nuevo
    assert D(r["costo_por_unidad"]) == costo_del_lote(api, nuevo) != costo_del_lote(api, viejo)
    assert [(f["codigo"], f["usado"], f["estado"]) for f in r["lotes"]] == [(nuevo, True, "LISTA"), (viejo, False, "CERRADA")]
    assert D(r["lotes"][0]["unidades"]) == 4 and D(r["lotes"][1]["costo_por_unidad"]) == costo_del_lote(api, viejo)
    assert r["avisos"] == []


def test_the_margin_is_over_the_price_and_each_loaded_tax_goes_on_top(api):
    codigo = un_producto(api)
    lote = un_lote(api, codigo, "4", estado="LISTA", envio="2026-10-25")
    iva = un_impuesto(api, "IVA ventas", "0.210")
    un_impuesto(api, "Ingresos Brutos", "0.035")
    costo = costo_del_lote(api, lote)
    r = preview(api, codigo, "30")
    neto = (costo / D("0.7")).quantize(D("0.01"), ROUND_HALF_UP)
    assert D(r["precio_neto"]) == neto and D(r["margen_pct"]) == 30 and r["sin_impuestos"] is False
    assert [i["nombre"] for i in r["impuestos"]] == ["IVA ventas", "Ingresos Brutos"]
    assert D(r["impuestos"][0]["monto"]) == (neto * D("0.21")).quantize(D("0.0001"), ROUND_HALF_UP)
    assert D(r["total_impuestos"]) == sum(D(i["monto"]) for i in r["impuestos"])
    assert D(r["precio_final"]) == neto + D(r["total_impuestos"])
    # A deactivated tax is not applied.
    assert api.post(f"/impuestos/{iva}/activo", json={"activo": False}).status_code == 200
    despues = preview(api, codigo, "30")
    assert [i["nombre"] for i in despues["impuestos"]] == ["Ingresos Brutos"]


def test_without_loaded_taxes_the_final_price_is_the_net_one_and_the_notice_flag_is_on(api):
    codigo = un_producto(api)
    un_lote(api, codigo, "4", estado="LISTA", envio="2026-10-25")
    r = preview(api, codigo, "30")
    assert r["sin_impuestos"] is True and r["impuestos"] == [] and r["precio_final"] == r["precio_neto"]


def test_a_margin_of_100_or_more_or_negative_is_a_422_and_an_unknown_product_a_404(api):
    codigo = un_producto(api)
    for margen in ("100", "-1", "30.55"):
        assert api.get(f"/productos/{codigo}/precio-desde-lotes", params={"margen": margen}).status_code == 422, margen
    assert api.get("/productos/PRD-9999/precio-desde-lotes", params={"margen": "30"}).status_code == 404


def test_the_gerente_reads_the_price_and_saves_it_as_a_new_dated_row_the_taller_does_neither(api):
    codigo = un_producto(api)
    un_lote(api, codigo, "4", estado="LISTA", envio="2026-10-25")
    un_impuesto(api, "IVA ventas", "0.210")
    como("gerente")
    r = preview(api, codigo, "30")
    guardado = api.post(f"/productos/{codigo}/precio-venta", json={
        "precio_ars": r["precio_neto"], "margen": "0.300", "nota": "Margen 30 % sobre el costo del lote"})
    assert guardado.status_code == 201, guardado.text
    fila = guardado.json()
    assert D(fila["precio_ars"]) == D(r["precio_neto"]) and D(fila["margen"]) == D("0.3") and fila["creado_por"] == "prueba-precio"
    assert D(fila["precio_final"]) == D(r["precio_final"])  # what was previewed is what the history shows
    segundo = api.post(f"/productos/{codigo}/precio-venta", json={"precio_ars": "99999", "margen": "0.400"})
    assert segundo.status_code == 201  # append-only: a second row, nothing is overwritten
    historial = api.get(f"/productos/{codigo}/precio-venta").json()
    assert [D(p["margen"]) for p in historial] == [D("0.4"), D("0.3")]
    como("taller")
    assert api.get(f"/productos/{codigo}/precio-desde-lotes", params={"margen": "30"}).status_code == 403
    assert api.post(f"/productos/{codigo}/precio-venta", json={"precio_ars": "10"}).status_code == 403
    como("admin")
    assert len(api.get(f"/productos/{codigo}/precio-venta").json()) == 2
