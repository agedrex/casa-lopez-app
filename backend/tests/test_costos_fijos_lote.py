"""Grid save of a month of fixed costs (grillas-costos T2, S5 and S6): `POST /costos-fijos/lote`, against PostgreSQL.

One transaction, admin only. A pending amount is filled in place; any other change is a NEW row that replaces the old
one (the old one stays and stops counting). Skipped without TEST_DATABASE_URL (each test runs in a rolled-back
transaction). Seeds used: month 2026-10, GF-0001..0007 with an amount (ficticio), GF-0008..0015 pending.
"""

from decimal import Decimal as D

import pytest
from sqlalchemy import func, select

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import GastoPeriodo
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)

PERIODO = "2026-10"
CON_MONTO = "GF-0001"  # Sueldo Mariano, FABRICA / SUELDOS, 1.000.000, ficticio
PENDIENTE = "GF-0010"  # Luz de la fábrica, FABRICA / SERVICIOS, no amount yet


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="admin-de-prueba", email="a@x.com", role=role))


def filas(api):
    """Every row of every month, replaced ones included, with all its columns."""
    columnas = [c for c in GastoPeriodo.__table__.columns if c.name != "created_at"]
    return [dict(f._mapping) for f in api.session.execute(select(*columnas).order_by(GastoPeriodo.id)).all()]


def total(mes):
    return D(mes["total_fabrica"]) + D(mes["total_tienda"])


def por_codigo(mes, codigo):
    return next(g for g in mes["gastos"] if g["codigo"] == codigo)


def lote(api, cambios=(), nuevos=(), periodo=PERIODO):
    return api.post("/costos-fijos/lote", json={"periodo": periodo, "cambios": list(cambios), "nuevos": list(nuevos)})


def nuevo(**cambios):
    return {"concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS", **cambios}


def test_a_pending_amount_is_filled_in_place_without_a_new_row(api):
    como("admin")
    antes = api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    cantidad = len(filas(api))
    respuesta = lote(api, [{"codigo": PENDIENTE, "monto": "45000.5"}])
    assert respuesta.status_code == 200, respuesta.text
    despues = respuesta.json()
    assert len(filas(api)) == cantidad  # same row, no replacement
    gasto = por_codigo(despues, PENDIENTE)
    assert D(gasto["monto_ars_del_mes"]) == D("45000.5") and gasto["reemplaza_a"] is None
    assert despues["pendientes"] == antes["pendientes"] - 1 and total(despues) - total(antes) == D("45000.5")
    assert api.get("/costos-fijos", params={"periodo": PERIODO}).json() == despues


def test_a_new_amount_on_a_row_with_amount_is_a_new_row_that_replaces_it_and_the_old_one_stays(api):
    como("admin")
    antes = api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    viejo = por_codigo(antes, CON_MONTO)
    todas = filas(api)
    despues = lote(api, [{"codigo": CON_MONTO, "monto": "1200000"}]).json()
    assert len(despues["gastos"]) == len(antes["gastos"])  # replaced, not added
    assert CON_MONTO not in {g["codigo"] for g in despues["gastos"]}  # the old one no longer counts
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == CON_MONTO)
    assert D(nueva["monto_ars_del_mes"]) == D("1200000") and nueva["codigo"] not in {g["codigo"] for g in antes["gastos"]}
    assert (nueva["concepto"], nueva["fabrica_o_tienda"], nueva["categoria"], nueva["persona"], nueva["ficticio"]) == (
        viejo["concepto"], viejo["fabrica_o_tienda"], viejo["categoria"], viejo["persona"], viejo["ficticio"])
    assert total(despues) - total(antes) == D("200000")  # only the new amount counts
    despues_de = filas(api)
    assert len(despues_de) == len(todas) + 1 and despues_de[:len(todas)] == todas  # the old row is untouched
    guardada = api.session.scalar(select(GastoPeriodo).where(GastoPeriodo.codigo == CON_MONTO))
    assert guardada.monto_ars_del_mes == D(viejo["monto_ars_del_mes"]) and guardada.reemplaza_a_id is None


@pytest.mark.parametrize("campo, valor", [
    ("monto", "7"), ("concepto", "Sueldo Mariano (nuevo)"), ("fabrica_o_tienda", "TIENDA"), ("categoria", "OTROS"),
])
def test_changing_amount_concept_area_or_category_of_a_row_with_amount_replaces_it(api, campo, valor):
    como("admin")
    antes = api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    viejo = por_codigo(antes, CON_MONTO)
    despues = lote(api, [{"codigo": CON_MONTO, campo: valor}]).json()
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == CON_MONTO)
    esperado = {"monto_ars_del_mes": viejo["monto_ars_del_mes"], "concepto": viejo["concepto"],
                "fabrica_o_tienda": viejo["fabrica_o_tienda"], "categoria": viejo["categoria"]}
    esperado["monto_ars_del_mes" if campo == "monto" else campo] = valor
    assert D(nueva["monto_ars_del_mes"]) == D(esperado["monto_ars_del_mes"])
    assert {k: nueva[k] for k in ("concepto", "fabrica_o_tienda", "categoria")} == {
        k: esperado[k] for k in ("concepto", "fabrica_o_tienda", "categoria")}
    assert (nueva["persona"], nueva["ficticio"]) == (viejo["persona"], viejo["ficticio"])  # the rest is copied
    assert CON_MONTO not in {g["codigo"] for g in despues["gastos"]}


def test_a_pending_row_with_a_concept_change_is_replaced_not_edited_in_place(api):
    como("admin")
    cantidad = len(filas(api))
    despues = lote(api, [{"codigo": PENDIENTE, "concepto": "Luz y gas de la fábrica", "monto": "500"}]).json()
    assert len(filas(api)) == cantidad + 1
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == PENDIENTE)
    assert nueva["concepto"] == "Luz y gas de la fábrica" and D(nueva["monto_ars_del_mes"]) == D("500")
    viejo = api.session.scalar(select(GastoPeriodo).where(GastoPeriodo.codigo == PENDIENTE))
    assert viejo.monto_ars_del_mes is None and viejo.concepto == "Luz de la fábrica"


@pytest.mark.parametrize("cambio", [
    {"codigo": CON_MONTO},                                               # nothing to change
    {"codigo": CON_MONTO, "monto": "1000000"},                           # same amount
    {"codigo": CON_MONTO, "monto": "1000000.0000", "categoria": "SUELDOS", "fabrica_o_tienda": "FABRICA"},
    {"codigo": CON_MONTO, "concepto": "Sueldo Mariano (consumos y moldes)"},  # same concept
    {"codigo": PENDIENTE},                                               # a pending row left pending
])
def test_a_batch_without_real_changes_writes_nothing(api, cambio):
    como("admin")
    antes, vista = filas(api), api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    respuesta = lote(api, [cambio])
    assert respuesta.status_code == 200, respuesta.text
    assert filas(api) == antes and respuesta.json() == vista


def test_the_rows_that_do_not_change_are_not_changed_by_a_batch(api):
    como("admin")
    antes = filas(api)
    codigos_tocados = {CON_MONTO, PENDIENTE}
    assert lote(api, [{"codigo": CON_MONTO, "monto": "9"}, {"codigo": PENDIENTE, "monto": "3"}],
                [nuevo()]).status_code == 200
    despues = {f["codigo"]: f for f in filas(api)}
    for fila in antes:
        if fila["codigo"] not in codigos_tocados:
            assert despues[fila["codigo"]] == fila, fila["codigo"]
    assert despues[CON_MONTO] == next(f for f in antes if f["codigo"] == CON_MONTO)  # a corrected row is never overwritten


def test_a_row_of_another_month_is_refused_and_nothing_is_saved(api):
    como("admin")
    antes = filas(api)
    respuesta = lote(api, [{"codigo": PENDIENTE, "monto": "5"}, {"codigo": CON_MONTO, "monto": "5"}], periodo="2026-11")
    assert respuesta.status_code == 422 and PENDIENTE in respuesta.json()["detail"] and "2026-11" in respuesta.json()["detail"]
    assert filas(api) == antes


def test_a_row_that_was_already_replaced_is_a_conflict_that_names_the_current_one(api):
    como("admin")
    primera = api.post(f"/costos-fijos/{CON_MONTO}/corregir", json={"monto_ars_del_mes": "100"}).json()
    actual = next(g for g in primera["gastos"] if g["reemplaza_a"] == CON_MONTO)
    antes = filas(api)
    respuesta = lote(api, [{"codigo": PENDIENTE, "monto": "5"}, {"codigo": CON_MONTO, "monto": "200"}])
    assert respuesta.status_code == 409 and actual["codigo"] in respuesta.json()["detail"]
    assert filas(api) == antes  # the pending amount of the first row was not saved either
    # the current row of the chain can be corrected
    assert lote(api, [{"codigo": actual["codigo"], "monto": "300"}]).status_code == 200


def test_a_pending_row_that_was_replaced_cannot_be_filled_in_the_batch(api):
    como("admin")
    assert api.post(f"/costos-fijos/{PENDIENTE}/corregir", json={"monto_ars_del_mes": "50"}).status_code == 201
    antes = filas(api)
    assert lote(api, [{"codigo": PENDIENTE, "monto": "60"}]).status_code == 409
    assert filas(api) == antes


@pytest.mark.parametrize("codigo", [CON_MONTO, PENDIENTE])
def test_a_negative_amount_is_refused_by_the_route(api, codigo):
    como("admin")
    antes = filas(api)
    assert lote(api, [{"codigo": codigo, "monto": "-0.01"}]).status_code == 422
    assert lote(api, nuevos=[nuevo(monto_ars_del_mes="-1")]).status_code == 422
    assert filas(api) == antes


def test_a_negative_amount_is_refused_by_the_service_even_without_the_route(api):
    antes = filas(api)
    with pytest.raises(servicios.DatosInvalidos, match="negativo"):
        servicios.guardar_gastos_en_lote(api.session, PERIODO, [{"codigo": CON_MONTO, "monto": D("-1")}], [])
    assert filas(api) == antes


def test_an_unknown_expense_is_not_found_and_nothing_is_saved(api):
    como("admin")
    antes = filas(api)
    respuesta = lote(api, [{"codigo": PENDIENTE, "monto": "5"}, {"codigo": "GF-9999", "monto": "5"}], [nuevo()])
    assert respuesta.status_code == 404 and "GF-9999" in respuesta.json()["detail"]
    assert filas(api) == antes


def test_new_rows_are_created_with_consecutive_gf_codes_in_the_given_month(api):
    como("admin")
    ultimo = api.session.scalar(select(func.max(GastoPeriodo.codigo)).where(GastoPeriodo.codigo.like("GF-%")))
    siguiente = int(ultimo.split("-")[1]) + 1
    respuesta = lote(api, nuevos=[nuevo(concepto="Seguro", monto_ars_del_mes="800", nota_fuente="Póliza 12"),
                                  nuevo(concepto="Limpieza", fabrica_o_tienda="FABRICA", categoria="SERVICIOS")],
                     periodo="2027-01")
    assert respuesta.status_code == 200, respuesta.text
    mes = respuesta.json()
    assert mes["periodo"] == "2027-01"
    assert [g["codigo"] for g in mes["gastos"]] == [f"GF-{siguiente:04d}", f"GF-{siguiente + 1:04d}"]
    seguro, limpieza = mes["gastos"]
    assert (seguro["concepto"], D(seguro["monto_ars_del_mes"]), seguro["nota_fuente"], seguro["fabrica_o_tienda"]) == (
        "Seguro", D("800"), "Póliza 12", "TIENDA")
    assert limpieza["monto_ars_del_mes"] is None and mes["pendientes"] == 1 and total(mes) == D("800")
    assert seguro["reemplaza_a"] is None and seguro["ficticio"] is False


def test_changes_and_new_rows_travel_together_and_take_consecutive_codes(api):
    como("admin")
    ultimo = api.session.scalar(select(func.max(GastoPeriodo.codigo)).where(GastoPeriodo.codigo.like("GF-%")))
    siguiente = int(ultimo.split("-")[1]) + 1
    mes = lote(api, [{"codigo": CON_MONTO, "monto": "5"}, {"codigo": PENDIENTE, "monto": "6"}], [nuevo()]).json()
    nueva_correccion = next(g for g in mes["gastos"] if g["reemplaza_a"] == CON_MONTO)
    assert nueva_correccion["codigo"] == f"GF-{siguiente:04d}"
    assert por_codigo(mes, PENDIENTE)["monto_ars_del_mes"] is not None
    assert por_codigo(mes, f"GF-{siguiente + 1:04d}")["concepto"] == "Seguro"


def test_a_new_row_may_name_a_person_and_an_unknown_person_saves_nothing(api):
    como("admin")
    antes = filas(api)
    desconocida = lote(api, [{"codigo": PENDIENTE, "monto": "5"}], [nuevo(persona="PER-9999")])
    assert desconocida.status_code == 422 and "PER-9999" in desconocida.json()["detail"]
    assert filas(api) == antes
    persona = api.get("/costos-fijos", params={"periodo": PERIODO}).json()["gastos"][0]["persona"]
    if persona:
        assert lote(api, nuevos=[nuevo(persona=persona)]).status_code == 200


def test_a_blank_concept_in_a_new_row_or_a_change_is_refused(api):
    como("admin")
    antes = filas(api)
    assert lote(api, nuevos=[nuevo(concepto="   ")]).status_code == 422
    assert lote(api, [{"codigo": CON_MONTO, "concepto": "   "}]).status_code == 422
    assert lote(api, [{"codigo": CON_MONTO, "concepto": ""}]).status_code == 422
    assert filas(api) == antes


def test_a_clean_batch_with_a_failing_new_row_saves_nothing(api):
    como("admin")
    antes = filas(api)
    respuesta = lote(api, [{"codigo": CON_MONTO, "monto": "5"}, {"codigo": PENDIENTE, "monto": "6"}],
                     [nuevo(), nuevo(persona="PER-9999")])
    assert respuesta.status_code == 422
    assert filas(api) == antes
    assert api.get("/costos-fijos", params={"periodo": PERIODO}).json()["pendientes"] == 8


def test_clearing_the_amount_of_a_row_that_has_one_is_refused(api):
    como("admin")
    antes = filas(api)
    respuesta = lote(api, [{"codigo": CON_MONTO, "monto": None}])
    assert respuesta.status_code == 422 and CON_MONTO in respuesta.json()["detail"]
    assert filas(api) == antes


def test_an_empty_batch_a_repeated_row_and_more_than_500_rows_are_refused(api):
    como("admin")
    antes = filas(api)
    assert lote(api).status_code == 422
    repetido = lote(api, [{"codigo": CON_MONTO, "monto": "5"}, {"codigo": CON_MONTO, "monto": "6"}])
    assert repetido.status_code == 422 and "repetido" in repetido.json()["detail"]
    demasiadas = lote(api, nuevos=[nuevo(concepto=f"Fila {n}") for n in range(501)])
    assert demasiadas.status_code == 422 and "500" in demasiadas.json()["detail"]
    assert filas(api) == antes


@pytest.mark.parametrize("cuerpo", [
    {"cambios": [{"codigo": CON_MONTO, "monto": "5"}]},                       # no month
    {"periodo": "2026-13", "cambios": [{"codigo": CON_MONTO, "monto": "5"}]},  # not AAAA-MM
    {"periodo": PERIODO, "cambios": [{"monto": "5"}]},                         # a change without its code
    {"periodo": PERIODO, "cambios": [{"codigo": CON_MONTO, "categoria": "MAGIA"}]},
    {"periodo": PERIODO, "cambios": [{"codigo": CON_MONTO, "fabrica_o_tienda": "OTRA"}]},
    {"periodo": PERIODO, "cambios": [{"codigo": CON_MONTO, "ficticio": False}]},  # not editable here
    {"periodo": PERIODO, "nuevos": [{"concepto": "x", "fabrica_o_tienda": "TIENDA"}]},  # no category
    {"periodo": PERIODO, "nuevos": [{"fabrica_o_tienda": "TIENDA", "categoria": "OTROS"}]},  # no concept
])
def test_malformed_bodies_are_refused_before_saving(api, cuerpo):
    como("admin")
    antes = filas(api)
    assert api.post("/costos-fijos/lote", json=cuerpo).status_code == 422
    assert filas(api) == antes


@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_only_the_admin_can_save_a_batch_of_fixed_costs(api, role):
    como("admin")
    antes = filas(api)
    como(role)
    assert lote(api, [{"codigo": PENDIENTE, "monto": "5"}], [nuevo()]).status_code == 403
    assert filas(api) == antes


def test_the_batch_route_does_not_shadow_the_single_row_routes(api):
    como("admin")
    assert api.post(f"/costos-fijos/{PENDIENTE}/monto", json={"monto_ars_del_mes": "11"}).status_code == 200
    assert api.post(f"/costos-fijos/{CON_MONTO}/corregir", json={"monto_ars_del_mes": "12"}).status_code == 201
    assert api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-05"}).status_code == 201
