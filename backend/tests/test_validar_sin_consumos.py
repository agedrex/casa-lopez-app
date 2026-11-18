"""S1 (odd/tasks/mejoras-qa-staging.md): an empty model cannot be validated and an empty consumption sheet cannot be completed
or validated. Integration tests against disposable PostgreSQL (skipped without TEST_DATABASE_URL), each in a rolled back transaction.

"Empty" = every consumption (leather, lining, flex, goma EVA, herrajes, hilo y cemento) is missing or 0 and the model has no
supplies; for a sheet, no row has a quantity above 0. The admin still sends a blank sheet to the workshop (that is the workflow).
"""

from decimal import Decimal as D

import pytest
from sqlalchemy import select

from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import FormularioConsumo, Modelo

from test_costos_fijos_correccion_integration import api  # noqa: E402,F401  (fixture; its client also carries `.session`)

MENSAJE_MODELO = "El modelo no tiene consumos cargados: cargá el cuero, el forro u otro consumo antes de validarlo."
MENSAJE_COMPLETAR = "La hoja no tiene ninguna cantidad cargada: completá al menos una fila antes de enviarla."
MENSAJE_VALIDAR = "La hoja no tiene ninguna cantidad cargada: no se puede validar vacía."

SIN_CONSUMOS = {
    "cuero_m2_por_unidad": "0", "forro": None, "forro_m2_por_unidad": None, "flex_m2_por_unidad": None,
    "goma_eva_m2_por_unidad": None, "herrajes_usd_por_unidad": None, "hilo_y_cemento": None,
    "confeccion_estimada_ars": None, "horas_de_confeccion": None, "origen_de_los_consumos": "ESTIMADO",
}


def como(role, usuario="admin-1"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=role))


def modelo_nuevo(api, nombre, **consumos):
    como("admin")
    respuesta = api.post("/modelos", json={
        "nombre_del_modelo": nombre, "categoria": "Billeteras", **{**SIN_CONSUMOS, **consumos}})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def validar_modelo(api, codigo, validado=True):
    return api.post(f"/modelos/{codigo}/validado", json={"validado": validado})


def hoja_enviada(api, nombre, cantidades=None):
    """A quick-create model with its sheet ENVIADO; the taller fills `cantidades` ({row name: quantity}) but does not complete it."""
    como("admin")
    datos = api.post("/productos/nuevo", json={"nombre": nombre, "categoria": "Billeteras"}).json()
    codigo = datos["formulario"]
    como("taller", "taller-1")
    hoja = api.get(f"/formularios/{codigo}").json()
    guardar(api, codigo, hoja, cantidades or {})
    return datos["modelo"], codigo


def guardar(api, codigo, hoja, cantidades):
    lineas = [{"seccion": l["seccion"], "nombre": l["nombre"], "comentario": l["comentario"],
               "cantidad": cantidades.get(l["nombre"])} for l in hoja["lineas"]]
    respuesta = api.put(f"/formularios/{codigo}", json={"articulo": hoja["articulo"], "nota": hoja["nota"], "lineas": lineas})
    assert respuesta.status_code == 200, respuesta.text


def estado_de(api, codigo):
    return api.session.scalar(select(FormularioConsumo.estado).where(FormularioConsumo.codigo == codigo))


# --- Model ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("consumos", [
    {},  # leather 0 and everything else missing
    {"forro_m2_por_unidad": "0", "flex_m2_por_unidad": "0", "goma_eva_m2_por_unidad": "0", "herrajes_usd_por_unidad": "0",
     "hilo_y_cemento": "0"},  # everything 0
])
def test_an_empty_model_cannot_be_validated(api, consumos):
    codigo = modelo_nuevo(api, "Zz Modelo vacío", **consumos)
    respuesta = validar_modelo(api, codigo)
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": MENSAJE_MODELO}
    assert api.get(f"/modelos/{codigo}").json()["validado"] is False


def test_a_model_from_the_quick_create_without_consumptions_cannot_be_validated(api):
    como("admin")
    codigo = api.post("/productos/nuevo", json={"nombre": "Zz Alta rápida", "categoria": "Billeteras"}).json()["modelo"]
    respuesta = validar_modelo(api, codigo)
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": MENSAJE_MODELO}


@pytest.mark.parametrize("consumos", [
    {"cuero_m2_por_unidad": "0.3"}, {"cuero_m2_por_unidad": "0", "forro_m2_por_unidad": "0.2", "forro": "MAT-FO02"},
    {"cuero_m2_por_unidad": "0", "flex_m2_por_unidad": "0.1"}, {"cuero_m2_por_unidad": "0", "herrajes_usd_por_unidad": "2"},
])
def test_a_model_with_any_consumption_above_zero_can_be_validated(api, consumos):
    codigo = modelo_nuevo(api, "Zz Modelo con consumo", **consumos)
    respuesta = validar_modelo(api, codigo)
    assert respuesta.status_code == 200 and respuesta.json()["validado"] is True


def test_a_seeded_model_still_validates_and_unvalidating_an_empty_model_is_still_allowed(api):
    como("admin")
    assert validar_modelo(api, "MOD-0001").json()["validado"] is True
    codigo = modelo_nuevo(api, "Zz Modelo vacío 2")
    assert validar_modelo(api, codigo, validado=False).json()["validado"] is False
    assert validar_modelo(api, "MOD-9999").status_code == 404


# --- Sheet ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cantidades", [{}, {"CUERO": "0", "FLEX": "0"}])
def test_a_sheet_without_any_quantity_cannot_be_completed(api, cantidades):
    _, codigo = hoja_enviada(api, "Zz Hoja vacía", cantidades)
    respuesta = api.post(f"/formularios/{codigo}/completar")
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": MENSAJE_COMPLETAR}
    assert estado_de(api, codigo) == "ENVIADO"
    como("admin")
    assert api.post(f"/formularios/{codigo}/completar").status_code == 422  # the admin neither


def test_a_sheet_with_one_quantity_above_zero_is_completed_and_validated(api):
    modelo, codigo = hoja_enviada(api, "Zz Hoja con cuero", {"CUERO": "0.4"})
    assert api.post(f"/formularios/{codigo}/completar").status_code == 200
    como("admin")
    assert api.post(f"/formularios/{codigo}/validar").status_code == 200
    assert D(api.get(f"/modelos/{modelo}").json()["cuero_m2_por_unidad"]) == D("0.4")


def test_a_completed_sheet_emptied_by_the_admin_cannot_be_validated_and_nothing_changes(api):
    modelo, codigo = hoja_enviada(api, "Zz Hoja vaciada", {"CUERO": "0.4"})
    assert api.post(f"/formularios/{codigo}/completar").status_code == 200
    como("admin")
    hoja = api.get(f"/formularios/{codigo}").json()
    guardar(api, codigo, hoja, {})
    respuesta = api.post(f"/formularios/{codigo}/validar")
    assert respuesta.status_code == 422 and respuesta.json() == {"detail": MENSAJE_VALIDAR}
    assert estado_de(api, codigo) == "COMPLETADO"
    detalle = api.get(f"/modelos/{modelo}").json()
    assert detalle["validado"] is False and detalle["cuero_m2_por_unidad"] is None


def test_the_admin_still_sends_a_blank_sheet_to_the_workshop(api):
    como("admin")
    codigo = api.post("/formularios", json={"articulo": "Zz Hoja en blanco"}).json()["codigo"]
    enviado = api.post(f"/formularios/{codigo}/enviar")
    assert enviado.status_code == 200 and enviado.json()["estado"] == "ENVIADO"
    assert api.post(f"/formularios/{codigo}/enviar").status_code == 200  # sending it again keeps working


def test_the_role_and_state_checks_come_before_the_empty_sheet_check(api):
    _, codigo = hoja_enviada(api, "Zz Hoja orden de reglas")
    como("admin")
    respuesta = api.post(f"/formularios/{codigo}/validar")  # ENVIADO, not COMPLETADO: the transition error wins
    assert respuesta.status_code == 409 and "completado" in respuesta.json()["detail"]
    como("gerente")
    assert api.post(f"/formularios/{codigo}/completar").status_code == 403
