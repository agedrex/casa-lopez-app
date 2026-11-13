"""Soft delete and fuller editing of fixed costs against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs in a rolled-back transaction. Seeds used: month 2026-10, GF-0001..0007 with an amount (ficticio),
GF-0008..0015 pending.
"""

from decimal import Decimal as D

import pytest
from sqlalchemy import func, select

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import GastoPeriodo
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)
from test_costos_fijos_lote import filas, lote, por_codigo, total

PERIODO = "2026-10"
CON_MONTO = "GF-0001"
OTRO_CON_MONTO = "GF-0002"
PENDIENTE = "GF-0010"


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="admin-de-prueba", email="a@x.com", role=role))


def mes(api):
    return api.get("/costos-fijos", params={"periodo": PERIODO}).json()


def lote_con(api, cambios=(), nuevos=(), anulados=(), periodo=PERIODO):
    return api.post("/costos-fijos/lote", json={
        "periodo": periodo, "cambios": list(cambios), "nuevos": list(nuevos), "anulados": list(anulados)})


def otra_persona(api, distinta_de):
    """A person code other than the one the row has now (the seed rows may already name the first one)."""
    return next(p["codigo"] for p in api.get("/personas").json() if p["codigo"] != distinta_de)


def test_an_annulled_row_leaves_the_list_and_the_totals_but_stays_in_the_database(api):
    como("admin")
    antes = mes(api)
    monto = D(por_codigo(antes, CON_MONTO)["monto_ars_del_mes"])
    todas = filas(api)
    respuesta = api.post(f"/costos-fijos/{CON_MONTO}/anular")
    assert respuesta.status_code == 200, respuesta.text
    despues = respuesta.json()
    assert CON_MONTO not in {g["codigo"] for g in despues["gastos"]}
    assert len(despues["gastos"]) == len(antes["gastos"]) - 1 and total(antes) - total(despues) == monto
    assert mes(api) == despues
    nuevas = filas(api)
    assert len(nuevas) == len(todas)  # nothing was deleted or added
    anulada = next(f for f in nuevas if f["codigo"] == CON_MONTO)
    assert anulada["anulado"] is True and {k: v for k, v in anulada.items() if k != "anulado"} == {
        k: v for k, v in next(f for f in todas if f["codigo"] == CON_MONTO).items() if k != "anulado"}


def test_annulling_a_pending_row_lowers_the_pending_count(api):
    como("admin")
    antes = mes(api)
    despues = api.post(f"/costos-fijos/{PENDIENTE}/anular").json()
    assert despues["pendientes"] == antes["pendientes"] - 1 and total(despues) == total(antes)


def test_annulling_twice_is_a_conflict_and_changes_nothing(api):
    como("admin")
    assert api.post(f"/costos-fijos/{CON_MONTO}/anular").status_code == 200
    antes = filas(api)
    segunda = api.post(f"/costos-fijos/{CON_MONTO}/anular")
    assert segunda.status_code == 409 and "anulado" in segunda.json()["detail"]
    assert filas(api) == antes


def test_annulling_a_row_that_was_corrected_is_a_conflict_that_names_the_current_one(api):
    como("admin")
    primera = api.post(f"/costos-fijos/{CON_MONTO}/corregir", json={"monto_ars_del_mes": "100"}).json()
    actual = next(g for g in primera["gastos"] if g["reemplaza_a"] == CON_MONTO)
    antes = filas(api)
    respuesta = api.post(f"/costos-fijos/{CON_MONTO}/anular")
    assert respuesta.status_code == 409 and actual["codigo"] in respuesta.json()["detail"]
    assert filas(api) == antes
    assert api.post(f"/costos-fijos/{actual['codigo']}/anular").status_code == 200  # the current one can go


def test_annulling_an_unknown_row_is_not_found(api):
    como("admin")
    assert api.post("/costos-fijos/GF-9999/anular").status_code == 404


def test_an_annulled_row_cannot_be_corrected_nor_filled_in(api):
    como("admin")
    api.post(f"/costos-fijos/{CON_MONTO}/anular")
    api.post(f"/costos-fijos/{PENDIENTE}/anular")
    antes = filas(api)
    assert api.post(f"/costos-fijos/{CON_MONTO}/corregir", json={"monto_ars_del_mes": "1"}).status_code == 409
    monto = api.post(f"/costos-fijos/{PENDIENTE}/monto", json={"monto_ars_del_mes": "1"})
    assert monto.status_code == 409 and "anulado" in monto.json()["detail"]
    assert lote(api, [{"codigo": CON_MONTO, "monto": "1"}]).status_code == 409
    assert lote(api, [{"codigo": PENDIENTE, "monto": "1"}]).status_code == 409
    assert filas(api) == antes


def test_copying_a_month_skips_annulled_rows(api):
    como("admin")
    api.post(f"/costos-fijos/{CON_MONTO}/anular")
    cantidad = len(mes(api)["gastos"])
    copia = api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-06"})
    assert copia.status_code == 201, copia.text
    assert len(copia.json()["gastos"]) == cantidad
    assert all(CON_MONTO not in (g["nota_fuente"] or "") for g in copia.json()["gastos"])


def test_a_month_whose_rows_are_all_annulled_can_be_the_target_of_a_copy(api):
    como("admin")
    api.post("/costos-fijos", json={"periodo": "2027-07", "concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"})
    codigo = api.get("/costos-fijos", params={"periodo": "2027-07"}).json()["gastos"][0]["codigo"]
    assert api.post(f"/costos-fijos/{codigo}/anular").status_code == 200
    assert api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-07"}).status_code == 201


def test_the_batch_annuls_in_the_same_transaction_as_changes_and_new_rows(api):
    como("admin")
    antes = mes(api)
    respuesta = lote_con(
        api, cambios=[{"codigo": PENDIENTE, "monto": "70"}], anulados=[CON_MONTO, OTRO_CON_MONTO],
        nuevos=[{"concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS", "monto_ars_del_mes": "5"}])
    assert respuesta.status_code == 200, respuesta.text
    despues = respuesta.json()
    codigos = {g["codigo"] for g in despues["gastos"]}
    assert not codigos & {CON_MONTO, OTRO_CON_MONTO} and PENDIENTE in codigos
    quitado = sum(D(por_codigo(antes, c)["monto_ars_del_mes"]) for c in (CON_MONTO, OTRO_CON_MONTO))
    assert total(despues) == total(antes) - quitado + D("75")


def test_a_rejected_batch_with_annulments_leaves_everything_unchanged(api):
    como("admin")
    antes = filas(api)
    vista = mes(api)
    nuevo = {"concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"}
    # unknown row, already corrected row, row of another month, unknown person in a new row: each one voids the batch
    assert lote_con(api, anulados=[CON_MONTO, "GF-9999"]).status_code == 404
    assert lote_con(api, anulados=[CON_MONTO], periodo="2026-11").status_code == 422
    assert lote_con(api, anulados=[CON_MONTO], nuevos=[{**nuevo, "persona": "PER-9999"}]).status_code == 422
    api.post(f"/costos-fijos/{OTRO_CON_MONTO}/corregir", json={"monto_ars_del_mes": "1"})
    despues_de_corregir = filas(api)
    assert lote_con(api, anulados=[CON_MONTO, OTRO_CON_MONTO]).status_code == 409
    assert filas(api) == despues_de_corregir
    assert len(despues_de_corregir) == len(antes) + 1 and vista["gastos"][0]["codigo"] == CON_MONTO


def test_the_same_code_in_changes_and_annulments_is_refused(api):
    como("admin")
    antes = filas(api)
    respuesta = lote_con(api, cambios=[{"codigo": CON_MONTO, "monto": "5"}], anulados=[CON_MONTO])
    assert respuesta.status_code == 422 and CON_MONTO in respuesta.json()["detail"]
    assert lote_con(api, anulados=[CON_MONTO, CON_MONTO]).status_code == 422
    assert filas(api) == antes


def test_an_annulment_only_batch_counts_toward_the_row_limit(api):
    como("admin")
    antes = filas(api)
    respuesta = lote_con(api, anulados=[f"GF-{n:04d}" for n in range(1, servicios.MAX_FILAS_POR_LOTE + 2)])
    assert respuesta.status_code == 422 and str(servicios.MAX_FILAS_POR_LOTE) in respuesta.json()["detail"]
    assert filas(api) == antes


# --- editing person and note -----------------------------------------------------------------------------------

def test_changing_the_person_of_a_row_creates_a_correction_that_keeps_the_rest(api):
    como("admin")
    antes = mes(api)
    viejo = por_codigo(antes, CON_MONTO)
    persona = otra_persona(api, viejo["persona"])
    cantidad = len(filas(api))
    despues = lote(api, [{"codigo": CON_MONTO, "persona": persona}]).json()
    assert len(filas(api)) == cantidad + 1
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == CON_MONTO)
    assert nueva["persona"] == persona
    assert nueva["monto_ars_del_mes"] == viejo["monto_ars_del_mes"] and nueva["concepto"] == viejo["concepto"]
    assert nueva["nota_fuente"] == f"Corrige {CON_MONTO}"
    assert total(despues) == total(antes)


@pytest.mark.parametrize("vacio", [None, ""])
def test_clearing_the_person_with_null_or_empty_string(api, vacio):
    como("admin")
    viejo = por_codigo(mes(api), CON_MONTO)
    if viejo["persona"] is None:  # give it a person first so that clearing is a real change
        lote(api, [{"codigo": CON_MONTO, "persona": otra_persona(api, None)}])
        viejo = next(g for g in mes(api)["gastos"] if g["reemplaza_a"] == CON_MONTO)
    despues = lote(api, [{"codigo": viejo["codigo"], "persona": vacio}]).json()
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == viejo["codigo"])
    assert nueva["persona"] is None


def test_an_unknown_person_in_a_change_is_refused_and_saves_nothing(api):
    como("admin")
    antes = filas(api)
    respuesta = lote(api, [{"codigo": PENDIENTE, "monto": "5"}, {"codigo": CON_MONTO, "persona": "PER-9999"}])
    assert respuesta.status_code == 422 and "PER-9999" in respuesta.json()["detail"]
    assert filas(api) == antes


def test_changing_the_note_creates_a_correction_with_that_note(api):
    como("admin")
    antes = mes(api)
    despues = lote(api, [{"codigo": CON_MONTO, "nota_fuente": "  Recibo de octubre  "}]).json()
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == CON_MONTO)
    assert nueva["nota_fuente"] == "Recibo de octubre" and total(despues) == total(antes)
    assert nueva["monto_ars_del_mes"] == por_codigo(antes, CON_MONTO)["monto_ars_del_mes"]


def test_a_note_change_on_a_pending_row_is_a_correction_not_an_in_place_edit(api):
    como("admin")
    cantidad = len(filas(api))
    despues = lote(api, [{"codigo": PENDIENTE, "nota_fuente": "Pendiente de factura", "monto": "9"}]).json()
    assert len(filas(api)) == cantidad + 1
    nueva = next(g for g in despues["gastos"] if g["reemplaza_a"] == PENDIENTE)
    assert nueva["nota_fuente"] == "Pendiente de factura" and D(nueva["monto_ars_del_mes"]) == D("9")
    assert api.session.scalar(select(GastoPeriodo.monto_ars_del_mes).where(GastoPeriodo.codigo == PENDIENTE)) is None


def test_resending_the_same_person_and_note_writes_nothing(api):
    como("admin")
    viejo = por_codigo(mes(api), CON_MONTO)
    antes = filas(api)
    cambio = {"codigo": CON_MONTO, "persona": viejo["persona"], "nota_fuente": viejo["nota_fuente"]}
    assert lote(api, [cambio]).status_code == 200
    assert lote(api, [{"codigo": CON_MONTO, "nota_fuente": ""}] if viejo["nota_fuente"] is None else [cambio]).status_code == 200
    assert filas(api) == antes


def test_a_pending_row_with_only_an_amount_is_still_filled_in_place(api):
    como("admin")
    cantidad = len(filas(api))
    despues = lote(api, [{"codigo": PENDIENTE, "monto": "45"}]).json()
    assert len(filas(api)) == cantidad and por_codigo(despues, PENDIENTE)["reemplaza_a"] is None


@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_only_the_admin_can_annul(api, role):
    como("admin")
    antes = filas(api)
    como(role)
    assert api.post(f"/costos-fijos/{CON_MONTO}/anular").status_code == 403
    assert lote_con(api, anulados=[CON_MONTO]).status_code == 403
    assert filas(api) == antes


def test_the_panel_and_the_factory_costs_ignore_annulled_rows(api):
    como("admin")
    antes = api.session.scalar(select(func.count()).select_from(GastoPeriodo).where(GastoPeriodo.anulado.is_(True)))
    assert antes == 0
    api.post(f"/costos-fijos/{CON_MONTO}/anular")
    fabrica = servicios._fijos_de_fabrica(api.session, [PERIODO])[PERIODO]
    assert fabrica.total_fabrica == sum((D(g["monto_ars_del_mes"] or 0) for g in mes(api)["gastos"] if g["fabrica_o_tienda"] == "FABRICA"), D(0))


def test_a_month_with_one_live_row_among_annulled_ones_still_refuses_a_copy(api):
    como("admin")
    for concepto in ("Seguro", "Internet"):
        creado = api.post("/costos-fijos", json={
            "periodo": "2027-08", "concepto": concepto, "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"})
        assert creado.status_code == 201, creado.text
    primera = api.get("/costos-fijos", params={"periodo": "2027-08"}).json()["gastos"][0]["codigo"]
    assert api.post(f"/costos-fijos/{primera}/anular").status_code == 200
    antes = api.session.scalar(select(func.count()).select_from(GastoPeriodo))
    assert api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-08"}).status_code == 409
    assert api.session.scalar(select(func.count()).select_from(GastoPeriodo)) == antes


def test_a_month_whose_only_live_row_is_a_correction_refuses_a_copy(api):
    como("admin")
    api.post("/costos-fijos", json={
        "periodo": "2027-09", "concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS",
        "monto_ars_del_mes": "10"})
    codigo = api.get("/costos-fijos", params={"periodo": "2027-09"}).json()["gastos"][0]["codigo"]
    assert api.post(f"/costos-fijos/{codigo}/corregir", json={"monto_ars_del_mes": "20"}).status_code == 201
    assert api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-09"}).status_code == 409


def test_the_sheet_export_skips_annulled_rows(api):
    como("admin")
    assert api.post(f"/costos-fijos/{PENDIENTE}/anular").status_code == 200
    exportados = {g["codigo"] for p in servicios.costos_fijos_de_todos_los_periodos(api.session) for g in p["gastos"]}
    assert PENDIENTE not in exportados and CON_MONTO in exportados


def test_a_month_with_every_row_annulled_leaves_the_period_list(api):
    como("admin")
    api.post("/costos-fijos", json={
        "periodo": "2027-10", "concepto": "Seguro", "fabrica_o_tienda": "TIENDA", "categoria": "OTROS"})
    assert "2027-10" in api.get("/costos-fijos/periodos").json()["periodos"]
    codigo = api.get("/costos-fijos", params={"periodo": "2027-10"}).json()["gastos"][0]["codigo"]
    assert api.post(f"/costos-fijos/{codigo}/anular").status_code == 200
    assert "2027-10" not in api.get("/costos-fijos/periodos").json()["periodos"]


def test_copying_only_some_categories_leaves_the_rest_out(api):
    como("admin")
    origen = mes(api)["gastos"]
    categoria = origen[0]["categoria"]
    esperado = [g for g in origen if g["categoria"] == categoria]
    copia = api.post("/costos-fijos/copiar", json={"desde": PERIODO, "hasta": "2027-08", "categorias": [categoria]})
    assert copia.status_code == 201, copia.text
    assert len(copia.json()["gastos"]) == len(esperado)
    assert {g["categoria"] for g in copia.json()["gastos"]} == {categoria}
