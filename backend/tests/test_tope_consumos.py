"""S1 (odd/tasks/mejoras-qa-staging.md): a per-unit cap on the consumptions of a model and on the quantities of a consumption sheet
(the QA typed 5000 m2 of leather). MAX_CONSUMO_POR_UNIDAD = 100 (m2 or units). Integration tests against disposable PostgreSQL
(skipped without TEST_DATABASE_URL), each in a rolled back transaction.
"""

from decimal import Decimal as D

import pytest

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.main import app

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)

SIN_CONSUMOS = {
    "cuero_m2_por_unidad": "0.3", "forro": None, "forro_m2_por_unidad": None, "flex_m2_por_unidad": None,
    "goma_eva_m2_por_unidad": None, "herrajes_usd_por_unidad": None, "hilo_y_cemento": None,
    "confeccion_estimada_ars": None, "horas_de_confeccion": None, "origen_de_los_consumos": "ESTIMADO",
}
MEDIDAS = [
    ("cuero_m2_por_unidad", "cuero"), ("forro_m2_por_unidad", "forro"), ("flex_m2_por_unidad", "flex"),
    ("goma_eva_m2_por_unidad", "goma EVA"),
]


def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def mensaje(que):
    return f"El consumo de {que} no puede superar 100 m² por unidad."


def cuerpo_modelo(nombre="Zz Tope", **cambios):
    consumos = {**SIN_CONSUMOS, **cambios}
    if consumos.get("forro_m2_por_unidad") is not None and consumos["forro"] is None:
        consumos["forro"] = "MAT-FO02"
    return {"nombre_del_modelo": nombre, "categoria": "Billeteras", **consumos}


def test_the_cap_is_100(api):
    assert servicios.MAX_CONSUMO_POR_UNIDAD == D("100")


@pytest.mark.parametrize("campo, que", MEDIDAS)
def test_a_new_model_above_the_cap_is_a_422_with_a_plain_message_and_is_not_saved(api, campo, que):
    como("admin")
    antes = len(api.get("/modelos").json())
    respuesta = api.post("/modelos", json=cuerpo_modelo(**{campo: "5000"}))
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": mensaje(que)}
    assert "_m2_" not in respuesta.text
    assert len(api.get("/modelos").json()) == antes


@pytest.mark.parametrize("campo, que", MEDIDAS)
def test_exactly_the_cap_is_accepted_and_a_hair_above_it_is_not(api, campo, que):
    como("admin")
    assert api.post("/modelos", json=cuerpo_modelo(**{campo: "100"})).status_code == 201
    respuesta = api.post("/modelos", json=cuerpo_modelo("Zz Tope 2", **{campo: "100.000001"}))
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": mensaje(que)}


def test_the_amounts_in_money_are_not_capped_as_if_they_were_m2(api):
    como("admin")
    respuesta = api.post("/modelos", json=cuerpo_modelo(herrajes_usd_por_unidad="500", confeccion_estimada_ars="12000"))
    assert respuesta.status_code == 201, respuesta.text


def cuerpo_consumos(**cambios):
    return {key: valor for key, valor in cuerpo_modelo(**cambios).items() if key not in ("nombre_del_modelo", "categoria")}


def test_changing_the_consumptions_of_a_model_above_the_cap_is_a_422_and_keeps_the_old_values(api):
    como("admin")
    antes = api.get("/modelos/MOD-0001").json()
    respuesta = api.post("/modelos/MOD-0001/consumos", json=cuerpo_consumos(cuero_m2_por_unidad="5000"))
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": mensaje("cuero")}
    assert api.get("/modelos/MOD-0001").json() == antes
    assert api.post("/modelos/MOD-0001/consumos", json=cuerpo_consumos(cuero_m2_por_unidad="100")).status_code == 200


def test_the_grid_save_refuses_the_whole_batch_naming_the_model_and_saves_nothing(api):
    como("admin")
    antes = [api.get(f"/modelos/MOD-000{n}").json() for n in (1, 2)]
    filas = [{"codigo": "MOD-0001", **cuerpo_consumos()}, {"codigo": "MOD-0002", **cuerpo_consumos(flex_m2_por_unidad="900")}]
    respuesta = api.post("/modelos/consumos/lote", json={"filas": filas})
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": f"MOD-0002: {mensaje('flex')}"}
    assert [api.get(f"/modelos/MOD-000{n}").json() for n in (1, 2)] == antes


# --- Sheet ------------------------------------------------------------------------------------------------------------

def hoja_del_taller(api, nombre):
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": nombre, "categoria": "Billeteras"}).json()
    como("taller", "taller-1")
    return datos["formulario"], api.get(f"/formularios/{datos['formulario']}").json()


def guardar(api, codigo, hoja, cantidades):
    lineas = [{"seccion": l["seccion"], "nombre": l["nombre"], "comentario": l["comentario"],
               "cantidad": cantidades.get(l["nombre"], l["cantidad"])} for l in hoja["lineas"]]
    return api.put(f"/formularios/{codigo}", json={"articulo": hoja["articulo"], "nota": hoja["nota"], "lineas": lineas})


@pytest.mark.parametrize("fila", ["CUERO", "FORRO / TELA", "GOMA EVA", "CARTÓN FIBRA", "CIERRE N5", "REMACHES"])
def test_a_sheet_row_of_material_or_supply_above_the_cap_is_a_422_and_the_sheet_is_not_changed(api, fila):
    codigo, hoja = hoja_del_taller(api, f"Zz Hoja tope {fila}")
    respuesta = guardar(api, codigo, hoja, {fila: "5000"})
    assert respuesta.status_code == 422
    assert respuesta.json() == {"detail": f"La cantidad de {fila} no puede superar 100 por unidad."}
    assert api.get(f"/formularios/{codigo}").json()["lineas"] == hoja["lineas"]


def test_a_sheet_row_with_exactly_the_cap_is_saved_and_hours_or_labour_rows_are_not_capped(api):
    codigo, hoja = hoja_del_taller(api, "Zz Hoja tope justo")
    respuesta = guardar(api, codigo, hoja, {"CUERO": "100", "HS. DE TRABAJO": "250", "Y/O MANO DE OBRA TALLER": "12000"})
    assert respuesta.status_code == 200, respuesta.text
    por_nombre = {l["nombre"]: l["cantidad"] for l in respuesta.json()["lineas"]}
    assert D(por_nombre["CUERO"]) == 100 and D(por_nombre["Y/O MANO DE OBRA TALLER"]) == 12000
    assert guardar(api, codigo, hoja, {"CUERO": "100.000001"}).status_code == 422
