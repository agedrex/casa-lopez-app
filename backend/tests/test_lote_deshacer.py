""""Deshacer" del estado de un lote (T5 / S3 de odd/tasks/ux-heuristicas.md).

Un lote vuelve UN estado atrás, y solo si el último cambio lo hizo el mismo usuario hace menos de 10 minutos. El retroceso
agrega una fila nueva al historial: nada se borra ni se edita. `estado_anterior` es pura; el resto corre contra PostgreSQL
descartable (se saltea sin TEST_DATABASE_URL).
"""

import pytest
from sqlalchemy import text

from backend import lote_estados
from backend.database import get_session
from backend.main import app
from test_api_integration import api  # noqa: F401  (fixture)
from test_lote_estados import como, lote


def historial(api, ruta):
    return api.get(ruta).json()["estados"]


def retrasar_el_cambio(minutos):
    """The history row of EN_CORTE was written `minutos` ago (the test transaction freezes now(), so it is moved by hand)."""
    session = app.dependency_overrides[get_session]()
    session.execute(text(
        "UPDATE costos.orden_estado SET created_at = now() - make_interval(mins => :m) WHERE estado = 'EN_CORTE'"), {"m": minutos})
    session.expire_all()  # the test shares one session with the API: a request has a fresh one


def avanzar(api, ruta, veces=1):
    for _ in range(veces):
        respuesta = api.post(f"{ruta}/avanzar")
        assert respuesta.status_code == 201, respuesta.text


@pytest.mark.parametrize("actual, anterior", [
    ("PLANIFICADA", None), ("EN_CORTE", "PLANIFICADA"), ("CORTADA", "EN_CORTE"),
    ("EN_CONFECCION", "CORTADA"), ("LISTA", "EN_CONFECCION"), ("CERRADA", "LISTA")])
def test_the_previous_state_is_the_one_before_in_the_cycle(actual, anterior):
    assert lote_estados.estado_anterior(actual) == anterior


def test_undo_goes_back_one_state_and_appends_a_row_without_touching_the_old_ones(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    antes = historial(api, ruta)
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 201, respuesta.text
    detalle = respuesta.json()
    assert detalle["estado"] == "PLANIFICADA"
    despues = detalle["estados"]
    assert [e["estado"] for e in despues] == ["PLANIFICADA", "EN_CORTE", "PLANIFICADA"]
    assert despues[:2] == antes  # the old rows are exactly as they were
    assert despues[2]["cambiado_por"] == "usuario-taller" and despues[2]["registrado_en"]
    assert api.get(ruta).json()["estado"] == "PLANIFICADA"


def test_undo_goes_back_from_a_late_state_even_with_leather_already_cut(api):
    ruta = lote(api)  # the leather is cut: the taller reaches CORTADA and EN_CONFECCION
    como("taller")
    avanzar(api, ruta, 3)  # EN_CORTE, CORTADA, EN_CONFECCION
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado"] == "CORTADA"  # the cut is kept: nothing to revert from EN_CONFECCION
    assert len(respuesta.json()["estados"]) == 5


def test_the_lot_can_advance_again_after_an_undo(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201
    avanzar(api, ruta)
    assert api.get(ruta).json()["estado"] == "EN_CORTE"
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201  # a new advance can be undone again


def test_undo_refuses_the_first_state_and_leaves_no_row(api):
    ruta = lote(api)
    como("taller")
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 409
    assert "Planificada" in respuesta.json()["detail"]
    assert len(historial(api, ruta)) == 1


def test_undo_refuses_a_closed_lot(api):
    ruta = lote(api)
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        assert api.post(f"{ruta}/estado", json={"estado": estado, "fecha": "2026-10-06"}).status_code == 201
    assert api.post(f"{ruta}/estado", json={"estado": "CERRADA", "fecha": "2026-10-20", "fecha_de_entrega": "2026-10-19"}).status_code == 201
    respuesta = api.post(f"{ruta}/estado/deshacer")  # same user (the fixture's admin) and just written: still refused
    assert respuesta.status_code == 409 and "cerrado" in respuesta.json()["detail"]
    detalle = api.get(ruta).json()
    assert detalle["estado"] == "CERRADA" and len(detalle["estados"]) == 6


def test_undo_refuses_a_change_made_by_someone_else(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller", usuario="taller-uno")
    avanzar(api, ruta)
    como("taller", usuario="taller-dos")
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 409 and "hiciste vos" in respuesta.json()["detail"]
    detalle = api.get(ruta).json()
    assert detalle["estado"] == "EN_CORTE" and len(detalle["estados"]) == 2


def test_undo_refuses_a_change_older_than_ten_minutes(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    retrasar_el_cambio(11)
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 409 and "10 minutos" in respuesta.json()["detail"]
    detalle = api.get(ruta).json()
    assert detalle["estado"] == "EN_CORTE" and len(detalle["estados"]) == 2


def test_undo_is_still_allowed_just_inside_the_ten_minutes(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    retrasar_el_cambio(9)
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201


@pytest.mark.parametrize("pasos, estado", [(1, "EN_CORTE"), (2, "CORTADA")])
def test_undo_refuses_going_back_over_leather_already_cut(api, pasos, estado):
    ruta = lote(api)  # the lot already has a CORTE movement
    como("taller")
    avanzar(api, ruta, pasos)
    respuesta = api.post(f"{ruta}/estado/deshacer")
    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya se cortó cuero de este lote: pedile a un administrador que lo corrija."
    detalle = api.get(ruta).json()
    assert detalle["estado"] == estado and len(detalle["estados"]) == pasos + 1  # no row, the movement stays


def test_undo_twice_in_a_row_goes_back_only_one_state(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201
    segundo = api.post(f"{ruta}/estado/deshacer")
    assert segundo.status_code == 409
    assert len(historial(api, ruta)) == 3


def test_undo_unknown_lot_and_roles(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    assert api.post("/ordenes/LOT-9999/estado/deshacer").status_code == 404
    como("gerente")
    assert api.post(f"{ruta}/estado/deshacer").status_code == 403
    como("admin", usuario="el-admin")
    avanzar(api, ruta)
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201  # the admin gets what the taller gets


def test_the_admin_state_endpoint_cannot_skip_ahead_after_an_undo(api):
    ruta = lote(api, con_cuero_cortado=False)
    como("taller")
    avanzar(api, ruta)
    assert api.post(f"{ruta}/estado/deshacer").status_code == 201  # back to PLANIFICADA
    como("admin")
    saltado = api.post(f"{ruta}/estado", json={"estado": "CORTADA", "fecha": "2026-11-18"})
    assert saltado.status_code == 409
    assert len(historial(api, ruta)) == 3
