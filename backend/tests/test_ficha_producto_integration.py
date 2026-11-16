"""Ficha de producto contra PostgreSQL local (se saltea sin TEST_DATABASE_URL): nombres de material, horas y color.

Semillas: MOD-0001 con cuero MAT-CU01 (Estándar), forro MAT-FO02, hilo y cemento MAT-HC01 (USD 2 el juego), colores sembrados.
"""

from decimal import Decimal as D

from test_api_integration import api, producto  # noqa: F401  (fixture and helper)


def test_the_recipe_lines_carry_the_material_names_and_keep_the_codes(api):
    ficha = producto(api)
    lineas = {l["etapa"]: l for l in ficha["receta"]}
    assert lineas["CUERO"]["material"] == "MAT-CU01" and lineas["CUERO"]["material_nombre"] == "Estándar"
    assert lineas["HILO_CEMENTO"]["material_nombre"] == "Hilo y cemento"
    assert all(l["material_nombre"] and not l["material_nombre"].startswith("MAT-") for l in ficha["receta"])
    assert ficha["cuero_nombre"] == "Estándar" and ficha["modelo_nombre"]


def test_the_hours_of_the_model_come_in_the_ficha_and_do_not_change_the_cost(api):
    antes = producto(api)
    modelo = api.get("/modelos/MOD-0001").json()
    consumos = {k: modelo[k] for k in (
        "cuero_m2_por_unidad", "forro", "forro_m2_por_unidad", "flex_m2_por_unidad", "goma_eva_m2_por_unidad",
        "herrajes_usd_por_unidad", "hilo_y_cemento", "confeccion_estimada_ars", "origen_de_los_consumos")}
    assert api.post("/modelos/MOD-0001/consumos", json={**consumos, "horas_de_confeccion": "3.5"}).status_code == 200
    despues = api.get(f"/productos/{antes['codigo']}").json()
    assert D(despues["horas_de_confeccion"]) == D("3.5")
    assert despues["costo_hoy"]["total_ars"] == antes["costo_hoy"]["total_ars"]


def test_the_color_is_set_changed_and_cleared_without_touching_saved_quotes(api):
    codigo = producto(api)["codigo"]
    assert api.post(f"/productos/{codigo}/cotizaciones", json={"tipo": "INICIAL", "fecha": "2026-09-03"}).status_code == 201
    color = api.post("/colores", json={"nombre": "Color de prueba"}).json()["nombre"]
    cambiada = api.put(f"/productos/{codigo}/color", json={"color": color})
    assert cambiada.status_code == 200 and cambiada.json()["color"] == color
    assert len(cambiada.json()["cotizaciones"]) == 1
    assert api.put(f"/productos/{codigo}/color", json={"color": None}).json()["color"] is None


def test_an_unknown_color_or_product_is_refused(api):
    codigo = producto(api)["codigo"]
    assert api.put(f"/productos/{codigo}/color", json={"color": "Color que no existe"}).status_code == 422
    assert api.put("/productos/PRD-9999/color", json={"color": None}).status_code == 404
