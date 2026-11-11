"""Grid save of consumptions (grillas-costos T1, S3 and S6): `POST /modelos/consumos/lote`, against PostgreSQL.

All or nothing, admin only; each row follows the single-model rule (resets `validado`, logs who / old / new).
Skipped without TEST_DATABASE_URL, like the other integration tests (each test runs in a rolled-back transaction).
"""

import logging
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import Modelo
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)

CAMPOS = ("cuero_m2_por_unidad", "forro_m2_por_unidad", "flex_m2_por_unidad", "goma_eva_m2_por_unidad",
          "herrajes_usd_por_unidad", "hilo_y_cemento", "confeccion_estimada_ars", "horas_de_confeccion",
          "origen_de_los_consumos")


def como(role, id="admin-de-prueba"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=id, email="a@x.com", role=role))


def fila(codigo, **cambios):
    return {"codigo": codigo, "cuero_m2_por_unidad": "0.5", "forro": "MAT-FO02", "forro_m2_por_unidad": "0.2",
            "flex_m2_por_unidad": "0.45", "goma_eva_m2_por_unidad": "0", "herrajes_usd_por_unidad": "2",
            "hilo_y_cemento": "1", "confeccion_estimada_ars": "12000", "horas_de_confeccion": None,
            "origen_de_los_consumos": "MEDIDO", **cambios}


def estado(api):
    """Every model as the database holds it: consumptions, forro and validado."""
    modelos = api.session.scalars(select(Modelo).order_by(Modelo.id)).all()
    for m in modelos:
        api.session.refresh(m)
    return {m.codigo: (m.forro_id, m.validado, *(getattr(m, c) for c in CAMPOS)) for m in modelos}


def validar(api, *codigos):
    for codigo in codigos:
        assert api.post(f"/modelos/{codigo}/validado", json={"validado": True}).status_code == 200


def test_a_batch_saves_every_row_and_answers_how_many_and_which(api):
    como("admin")
    respuesta = api.post("/modelos/consumos/lote", json={"filas": [
        fila("MOD-0001"), fila("MOD-0002", cuero_m2_por_unidad="0.75", forro=None, forro_m2_por_unidad="0")]})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"guardados": 2, "modelos": ["MOD-0001", "MOD-0002"]}
    uno, dos = api.get("/modelos/MOD-0001").json(), api.get("/modelos/MOD-0002").json()
    assert D(uno["cuero_m2_por_unidad"]) == D("0.5") and uno["forro"] == "MAT-FO02" and uno["origen_de_los_consumos"] == "MEDIDO"
    assert D(uno["flex_m2_por_unidad"]) == D("0.45") and D(uno["confeccion_estimada_ars"]) == D("12000")
    assert D(dos["cuero_m2_por_unidad"]) == D("0.75") and dos["forro"] is None  # the second row has its own values


def test_a_batch_row_gives_the_same_result_as_the_single_model_route(api):
    como("admin")
    assert api.post("/modelos/MOD-0001/consumos", json={k: v for k, v in fila("MOD-0001").items() if k != "codigo"}).status_code == 200
    por_modelo = estado(api)["MOD-0001"]
    assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0002")]}).status_code == 200
    por_lote = estado(api)["MOD-0002"]
    assert por_lote == por_modelo


def test_a_batch_resets_validado_of_every_row_and_only_of_those_rows(api):
    como("admin")
    validar(api, "MOD-0001", "MOD-0002", "MOD-0003")
    assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001"), fila("MOD-0002")]}).status_code == 200
    assert api.get("/modelos/MOD-0001").json()["validado"] is False
    assert api.get("/modelos/MOD-0002").json()["validado"] is False
    assert api.get("/modelos/MOD-0003").json()["validado"] is True  # not in the batch: untouched


def test_a_batch_logs_who_changed_each_model_with_the_previous_and_the_new_values(api, caplog):
    como("admin", id="quien-guarda")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert api.post("/modelos/consumos/lote", json={"filas": [
            fila("MOD-0001"), fila("MOD-0002", cuero_m2_por_unidad="0.75")]}).status_code == 200
    lineas = {codigo: " ".join(r.getMessage() for r in caplog.records if codigo in r.getMessage())
              for codigo in ("MOD-0001", "MOD-0002")}
    assert "quien-guarda" in lineas["MOD-0001"] and "0.250000" in lineas["MOD-0001"] and "0.5" in lineas["MOD-0001"]
    assert "quien-guarda" in lineas["MOD-0002"] and "0.900000" in lineas["MOD-0002"] and "0.75" in lineas["MOD-0002"]
    assert "MOD-0002" not in lineas["MOD-0001"]  # one line per model


def test_a_rejected_batch_logs_nothing_as_changed(api, caplog):
    como("admin")
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001"), fila("MOD-9999")]}).status_code == 404
    assert not [r for r in caplog.records if "consumptions changed" in r.getMessage()]


def test_one_row_with_an_invalid_forro_saves_nothing_and_the_error_names_its_model(api):
    como("admin")
    validar(api, "MOD-0001")
    antes = estado(api)
    respuesta = api.post("/modelos/consumos/lote", json={"filas": [
        fila("MOD-0001"), fila("MOD-0002", forro="MAT-CU01")]})  # a leather is not a lining
    assert respuesta.status_code == 422
    assert "MOD-0002" in respuesta.json()["detail"] and "MOD-0001" not in respuesta.json()["detail"]
    assert estado(api) == antes  # the valid first row was not saved, and kept its validado


def test_square_meters_of_forro_without_a_forro_refuses_the_batch_and_names_the_model(api):
    como("admin")
    antes = estado(api)
    respuesta = api.post("/modelos/consumos/lote", json={"filas": [
        fila("MOD-0001"), fila("MOD-0003", forro=None, forro_m2_por_unidad="0.3")]})
    assert respuesta.status_code == 422 and "MOD-0003" in respuesta.json()["detail"]
    assert estado(api) == antes


def test_a_row_for_a_model_that_does_not_exist_saves_nothing_and_names_it(api):
    como("admin")
    antes = estado(api)
    respuesta = api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001"), fila("MOD-9999"), fila("MOD-0002")]})
    assert respuesta.status_code == 404 and "MOD-9999" in respuesta.json()["detail"]
    assert estado(api) == antes


def test_an_empty_batch_is_refused(api):
    como("admin")
    antes = estado(api)
    respuesta = api.post("/modelos/consumos/lote", json={"filas": []})
    assert respuesta.status_code == 422 and "No hay cambios" in respuesta.json()["detail"]
    assert estado(api) == antes


def test_a_repeated_model_code_is_refused_and_nothing_is_saved(api):
    como("admin")
    antes = estado(api)
    respuesta = api.post("/modelos/consumos/lote", json={"filas": [
        fila("MOD-0001"), fila("MOD-0002"), fila("MOD-0001", cuero_m2_por_unidad="0.9")]})
    assert respuesta.status_code == 422 and "repetido" in respuesta.json()["detail"]
    assert estado(api) == antes


def test_more_than_500_rows_are_refused_and_nothing_is_saved(api):
    como("admin")
    antes = estado(api)
    filas = [fila("MOD-0001")] + [fila(f"MOD-{n:04d}") for n in range(5000, 5500)]  # 501 rows
    respuesta = api.post("/modelos/consumos/lote", json={"filas": filas})
    assert respuesta.status_code == 422 and "500" in respuesta.json()["detail"]
    assert estado(api) == antes


@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_only_the_admin_can_save_a_batch(api, role):
    como("admin")
    antes = estado(api)
    como(role)
    assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001")]}).status_code == 403
    assert estado(api) == antes


@pytest.mark.parametrize("campo", ["codigo", "forro", *CAMPOS])
def test_a_row_missing_any_field_is_refused_with_422_so_nothing_is_cleared_by_omission(api, campo):
    como("admin")
    antes = estado(api)
    incompleta = {k: v for k, v in fila("MOD-0002").items() if k != campo}
    assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001"), incompleta]}).status_code == 422
    assert estado(api) == antes


@pytest.mark.parametrize("extra", [{"validado": True}, {"nombre_del_modelo": "x"}, {"cuero_m2_por_unidad": "-1"},
                                   {"origen_de_los_consumos": "MAGIA"}])
def test_calculated_or_out_of_range_fields_are_refused_before_saving(api, extra):
    como("admin")
    antes = estado(api)
    assert api.post("/modelos/consumos/lote", json={"filas": [fila("MOD-0001"), fila("MOD-0002", **extra)]}).status_code == 422
    assert estado(api) == antes


def test_a_body_without_the_rows_is_refused(api):
    como("admin")
    assert api.post("/modelos/consumos/lote", json={}).status_code == 422
