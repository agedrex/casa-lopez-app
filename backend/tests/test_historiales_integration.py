"""Supplier price history and workshop payment history against the disposable local PostgreSQL
(skipped without TEST_DATABASE_URL). Seeds used: PRE-0007 (MAT-FL01 flex, 10000 ARS/m2, 2026-09-03, text PRV-0001) and
PRE-0008 (MAT-GE01 goma EVA, 5857 ARS/m2, text PRV-0002); talleres TAL-0001 to TAL-0003.
"""

from decimal import Decimal as D

from sqlalchemy import text

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from test_api_integration import api, dolar_nuevo, producto  # noqa: F401  (fixture and helpers)


def proveedor_nuevo(api, nombre="Rouez", **extra):
    respuesta = api.post("/proveedores", json={"nombre": nombre, **extra})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def precio_de(api, codigo, **cambios):
    cuerpo = {"material": "MAT-FL01", "precio": "11000", "moneda": "ARS", "unidad_del_precio": "m2",
              "vigente_desde": "2026-10-01", **cambios}
    return api.post(f"/proveedores/{codigo}/precios", json=cuerpo)


def serie(api, codigo, material="MAT-FL01", color=None):
    materiales = api.get(f"/proveedores/{codigo}/materiales").json()["materiales"]
    return next(s for s in materiales if s["material"] == material and s["color"] == color)


# --- Supplier ------------------------------------------------------------------------------------------------------

def test_a_supplier_sees_the_seeded_price_whose_text_is_its_code_even_without_the_link(api):
    proveedor_nuevo(api)  # PRV-0001, created after the seed
    cuerpo = api.get("/proveedores/PRV-0001/materiales").json()
    assert cuerpo["proveedor"] == "PRV-0001" and cuerpo["proveedor_nombre"] == "Rouez"
    assert [s["material"] for s in cuerpo["materiales"]] == ["MAT-FL01"]
    flex = cuerpo["materiales"][0]
    assert D(flex["ultimo_precio"]) == 10000 and flex["moneda"] == "ARS" and flex["cargas"] == 1
    assert flex["historial"][0]["codigo"] == "PRE-0007" and flex["historial"][0]["variacion_pct"] is None


def test_a_supplier_with_no_prices_has_an_empty_list_and_an_unknown_one_is_404(api):
    proveedor_nuevo(api, "Sin precios", codigo="PRV-0100")
    assert api.get("/proveedores/PRV-0100/materiales").json()["materiales"] == []
    assert api.get("/proveedores/PRV-9999/materiales").status_code == 404
    assert precio_de(api, "PRV-9999").status_code == 404


def test_loading_a_price_from_the_supplier_adds_a_linked_row_and_the_history_shows_the_variation(api):
    proveedor_nuevo(api)
    creado = precio_de(api, "PRV-0001", precio="11000", nota_fuente="  Lista de octubre ")
    assert creado.status_code == 201, creado.text
    assert creado.json()["proveedor"] == "PRV-0001" and creado.json()["nota_fuente"] == "Lista de octubre"
    assert precio_de(api, "PRV-0001", precio="16500", vigente_desde="2026-11-01").status_code == 201
    flex = serie(api, "PRV-0001")
    assert [(h["vigente_desde"], D(h["precio"]), h["variacion_pct"]) for h in flex["historial"]] == [
        ("2026-11-01", D("16500"), "50.00"), ("2026-10-01", D("11000"), "10.00"), ("2026-09-03", D("10000"), None)]
    assert flex["cargas"] == 3 and flex["variacion_total_pct"] == "65.00" and flex["variacion_ultima_pct"] == "50.00"
    assert isinstance(flex["ultimo_precio"], str)  # money travels as text
    enlazados = api.get("/precios", params={"material": "MAT-FL01"}).json()
    assert len(enlazados) == 3  # the same rows feed the materials page: nothing is duplicated


def test_the_link_is_stored_and_old_rows_are_never_changed(api):
    proveedor_nuevo(api)
    session = app.dependency_overrides[get_session]()  # the test session
    antes = session.execute(text("select codigo, precio, proveedor, proveedor_id from costos.precio_material "
                                 "where codigo = 'PRE-0007'")).one()
    assert precio_de(api, "PRV-0001").status_code == 201
    nuevo = session.execute(text("select proveedor, proveedor_id from costos.precio_material order by id desc limit 1")).one()
    assert nuevo.proveedor == "PRV-0001"
    assert nuevo.proveedor_id == session.execute(text("select id from costos.proveedor where codigo = 'PRV-0001'")).scalar_one()
    despues = session.execute(text("select codigo, precio, proveedor, proveedor_id from costos.precio_material "
                                   "where codigo = 'PRE-0007'")).one()
    assert tuple(antes) == tuple(despues)  # the seeded row is untouched (still linked only by its text)


def test_prices_of_other_suppliers_and_free_text_names_are_not_mixed_in(api):
    proveedor_nuevo(api, "Rouez")  # PRV-0001
    proveedor_nuevo(api, "Acropol")  # PRV-0002
    assert precio_de(api, "PRV-0002", material="MAT-GE01", precio="6000").status_code == 201
    assert api.post("/precios", json={"material": "MAT-FL01", "precio": "9", "moneda": "ARS", "unidad_del_precio": "m2",
                                      "vigente_desde": "2026-10-05", "proveedor": "Rouez"}).status_code == 201
    uno = [s["material"] for s in api.get("/proveedores/PRV-0001/materiales").json()["materiales"]]
    dos = [s["material"] for s in api.get("/proveedores/PRV-0002/materiales").json()["materiales"]]
    assert uno == ["MAT-FL01"] and dos == ["MAT-GE01"]
    assert serie(api, "PRV-0001")["cargas"] == 1  # the "Rouez" text row is not guessed to be PRV-0001
    assert serie(api, "PRV-0002", "MAT-GE01")["cargas"] == 2  # seeded PRE-0008 (text PRV-0002) plus the new one


def test_a_price_loaded_with_a_supplier_code_in_the_old_form_gets_linked(api):
    proveedor_nuevo(api)
    session = app.dependency_overrides[get_session]()
    api.post("/precios", json={"material": "MAT-FL01", "precio": "10500", "moneda": "ARS", "unidad_del_precio": "m2",
                               "vigente_desde": "2026-10-05", "proveedor": "PRV-0001"})
    assert session.execute(text("select proveedor_id is not null from costos.precio_material "
                                "order by id desc limit 1")).scalar_one() is True
    api.post("/precios", json={"material": "MAT-FL01", "precio": "10600", "moneda": "ARS", "unidad_del_precio": "m2",
                               "vigente_desde": "2026-10-06", "proveedor": "PRV-7777"})  # no such supplier: stays unlinked
    assert session.execute(text("select proveedor_id is null from costos.precio_material "
                                "order by id desc limit 1")).scalar_one() is True


def test_the_price_rules_of_the_materials_page_apply_to_the_supplier_page(api):
    proveedor_nuevo(api)
    assert precio_de(api, "PRV-0001", vigente_desde="2026-09-03").status_code == 409  # PRE-0007 already has that date
    assert precio_de(api, "PRV-0001", unidad_del_precio="cm").status_code == 422
    assert precio_de(api, "PRV-0001", material="MAT-NOPE").status_code == 422
    assert precio_de(api, "PRV-0001", precio="-1").status_code == 422
    assert precio_de(api, "PRV-0001", moneda="EUR").status_code == 422
    assert precio_de(api, "PRV-0001", proveedor="PRV-0002").status_code == 422  # the supplier is the URL, not the body
    assert serie(api, "PRV-0001")["cargas"] == 1  # nothing was stored by the refusals


def test_colors_make_separate_series_for_the_same_material(api):
    proveedor_nuevo(api)
    api.post("/colores", json={"nombre": "Negro"})
    assert precio_de(api, "PRV-0001", color="Negro", precio="12000").status_code == 201
    assert [s["color"] for s in api.get("/proveedores/PRV-0001/materiales").json()["materiales"]] == [None, "Negro"]


def test_only_an_admin_writes_the_supplier_prices_and_a_taller_does_not_read_them(api):
    proveedor_nuevo(api)
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="t", role="taller"))
    assert api.get("/proveedores/PRV-0001/materiales").status_code == 403
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="g", role="gerente"))
    assert api.get("/proveedores/PRV-0001/materiales").status_code == 200  # Abastecimiento is read only for a gerente
    assert precio_de(api, "PRV-0001").status_code == 403


# --- Workshop ------------------------------------------------------------------------------------------------------

def lote_de(api, codigo_producto, fecha, cantidad, pagado, taller="TAL-0001", cotizado="12500"):
    cuerpo = {"donde_se_hace": "EXTERNA", "taller": taller, "fecha_de_envio": fecha,
              "items": [{"producto": codigo_producto, "cantidad": cantidad,
                         "taller_precio_cotizado_por_unidad_ars": cotizado, "taller_precio_pagado_por_unidad_ars": pagado}]}
    respuesta = api.post("/ordenes", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def test_a_workshop_without_lots_has_an_empty_history_and_an_unknown_one_is_404(api):
    cuerpo = api.get("/talleres/TAL-0001/historial").json()
    assert cuerpo["taller"] == "TAL-0001" and cuerpo["lotes"] == [] and cuerpo["productos"] == []
    assert api.get("/talleres/TAL-9999/historial").status_code == 404


def test_the_history_lists_what_was_paid_per_lot_and_per_product_with_its_variation(api):
    carteras = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    otro = producto(api, quien_lo_confecciona="EXTERNA", nombre_propio="Otra cartera")["codigo"]
    dolar_nuevo(api)
    primero = lote_de(api, carteras, "2026-09-01", "10", "10000")
    segundo = lote_de(api, carteras, "2026-10-01", "20", "11000")
    tercero = lote_de(api, otro, "2026-11-01", "5", "8000")
    lote_de(api, carteras, "2026-10-15", "99", "1", taller="TAL-0002")  # another workshop: not in this history
    cuerpo = api.get("/talleres/TAL-0001/historial").json()
    assert [(l["lote"], l["fecha"], D(l["unidades"]), D(l["total_pagado"])) for l in cuerpo["lotes"]] == [
        (tercero, "2026-11-01", 5, 40000), (segundo, "2026-10-01", 20, 220000), (primero, "2026-09-01", 10, 100000)]
    assert [l["precio_pagado_promedio"] for l in cuerpo["lotes"]] == ["8000.0000", "11000.0000", "10000.0000"]
    assert [l["barra_pct"] for l in cuerpo["lotes"]] == [18, 100, 45]
    por_producto = {p["producto"]: p for p in cuerpo["productos"]}
    assert list(por_producto) == [otro, carteras]  # the most recently given first
    cartera = por_producto[carteras]
    assert cartera["lotes"] == 2 and D(cartera["unidades"]) == 30 and cartera["producto_nombre"]
    assert [(h["lote"], D(h["pagado"]), h["variacion_pct"]) for h in cartera["historial"]] == [
        (segundo, D("11000"), "10.00"), (primero, D("10000"), None)]
    assert [h["item"] for h in cartera["historial"]] == ["LIT-0002", "LIT-0001"]
    assert cartera["variacion_total_pct"] == "10.00" and D(cartera["ultimo_pagado"]) == 11000
    assert isinstance(cartera["historial"][0]["pagado"], str) and isinstance(cuerpo["lotes"][0]["total_pagado"], str)


def test_a_price_loaded_later_on_an_item_shows_up_in_the_history_without_storing_anything_new(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    dolar_nuevo(api)
    lote = lote_de(api, codigo, "2026-10-01", "10", None)
    antes = api.get("/talleres/TAL-0001/historial").json()
    assert antes["lotes"][0]["precio_pagado_promedio"] is None and antes["productos"][0]["ultimo_pagado"] is None
    assert antes["lotes"][0]["unidades"] == "10.000000" and D(antes["productos"][0]["historial"][0]["cotizado"]) == 12500
    api.post(f"/ordenes/{lote}/items/LIT-0001/precios", json={"pagado": "13000"})
    despues = api.get("/talleres/TAL-0001/historial").json()
    assert D(despues["lotes"][0]["total_pagado"]) == 130000 and D(despues["productos"][0]["ultimo_pagado"]) == 13000


def test_the_history_total_matches_what_the_workshop_list_says_it_charged(api):
    codigo = producto(api, quien_lo_confecciona="EXTERNA")["codigo"]
    dolar_nuevo(api)
    lote_de(api, codigo, "2026-09-01", "10", "10000")
    lote_de(api, codigo, "2026-10-01", "3", "11000")
    historial = api.get("/talleres/TAL-0001/historial").json()
    cobro = next(t for t in api.get("/talleres").json() if t["codigo"] == "TAL-0001")["cobro_total_ars"]
    assert sum(D(l["total_pagado"]) for l in historial["lotes"]) == D(cobro)


def test_gerente_and_admin_read_the_workshop_history_but_taller_does_not(api):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="g", role="gerente"))
    assert api.get("/talleres/TAL-0001/historial").status_code == 200
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="t", role="taller"))
    assert api.get("/talleres/TAL-0001/historial").status_code == 403
