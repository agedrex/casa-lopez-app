"""Correct a fixed cost / copy a month against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
Seeds used: period 2026-10 with fixed costs (some with an amount, some pending).
"""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import GastoPeriodo


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-correccion", role="cotizador"))
    try:
        with TestClient(app) as client:
            client.session = session
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def total(mes):
    return D(mes["total_fabrica"]) + D(mes["total_tienda"])


def cantidad_de_filas(api, periodo):
    return api.session.scalar(select(func.count()).select_from(GastoPeriodo).where(GastoPeriodo.periodo == periodo))


def un_fijo(api):
    return next(g for g in api.get("/costos-fijos").json()["gastos"] if g["monto_ars_del_mes"] is not None)


def nuevo_gasto(api, periodo, concepto, monto, lado="FABRICA", categoria="OTROS", **cambios):
    cuerpo = {"periodo": periodo, "concepto": concepto, "fabrica_o_tienda": lado, "categoria": categoria,
              **({} if monto is None else {"monto_ars_del_mes": monto}), **cambios}
    respuesta = api.post("/costos-fijos", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_correcting_replaces_the_row_in_the_month_and_keeps_the_old_one(api):
    antes = api.get("/costos-fijos").json()
    viejo = un_fijo(api)
    filas_antes = cantidad_de_filas(api, antes["periodo"])
    respuesta = api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "123456.5"})
    assert respuesta.status_code == 201, respuesta.text
    despues = respuesta.json()
    assert len(despues["gastos"]) == len(antes["gastos"])  # replaced, not added
    assert viejo["codigo"] not in {g["codigo"] for g in despues["gastos"]}
    nuevo = next(g for g in despues["gastos"] if g["reemplaza_a"] == viejo["codigo"])
    assert nuevo["codigo"] != viejo["codigo"] and D(nuevo["monto_ars_del_mes"]) == D("123456.5")
    assert (nuevo["concepto"], nuevo["fabrica_o_tienda"], nuevo["categoria"], nuevo["persona"], nuevo["ficticio"]) == (
        viejo["concepto"], viejo["fabrica_o_tienda"], viejo["categoria"], viejo["persona"], viejo["ficticio"])
    assert total(despues) - total(antes) == D("123456.5") - D(viejo["monto_ars_del_mes"])  # only the new amount counts
    assert cantidad_de_filas(api, antes["periodo"]) == filas_antes + 1  # the old row is still there
    guardado = api.session.scalar(select(GastoPeriodo).where(GastoPeriodo.codigo == viejo["codigo"]))
    assert guardado.monto_ars_del_mes == D(viejo["monto_ars_del_mes"]) and guardado.reemplaza_a_id is None
    assert api.get("/costos-fijos").json() == despues  # the same view when read again


def test_a_correction_takes_the_given_ficticio_and_note(api):
    viejo = un_fijo(api)
    despues = api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={
        "monto_ars_del_mes": "10", "nota": "Factura de octubre", "ficticio": not viejo["ficticio"]}).json()
    nuevo = next(g for g in despues["gastos"] if g["reemplaza_a"] == viejo["codigo"])
    assert nuevo["nota_fuente"] == "Factura de octubre" and nuevo["ficticio"] is (not viejo["ficticio"])


def test_a_zero_amount_is_a_valid_correction(api):
    viejo = un_fijo(api)
    despues = api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "0"}).json()
    assert D(next(g for g in despues["gastos"] if g["reemplaza_a"] == viejo["codigo"])["monto_ars_del_mes"]) == 0


def test_correcting_a_replaced_row_conflicts_but_the_current_one_can_be_corrected_again(api):
    viejo = un_fijo(api)
    primera = api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "100"}).json()
    actual = next(g for g in primera["gastos"] if g["reemplaza_a"] == viejo["codigo"])
    otra = api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "200"})
    assert otra.status_code == 409 and actual["codigo"] in otra.json()["detail"]
    segunda = api.post(f"/costos-fijos/{actual['codigo']}/corregir", json={"monto_ars_del_mes": "300"})
    assert segunda.status_code == 201
    final = next(g for g in segunda.json()["gastos"] if g["reemplaza_a"] == actual["codigo"])
    assert {viejo["codigo"], actual["codigo"]}.isdisjoint(g["codigo"] for g in segunda.json()["gastos"])
    assert api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "1"}).json()["detail"].endswith(
        f"{final['codigo']}.")  # the chain is followed to the row that counts


def test_invalid_or_unknown_corrections_write_nothing(api):
    viejo = un_fijo(api)
    filas = cantidad_de_filas(api, "2026-10")
    assert api.post(f"/costos-fijos/{viejo['codigo']}/corregir", json={"monto_ars_del_mes": "-1"}).status_code == 422
    assert api.post("/costos-fijos/GF-9999/corregir", json={"monto_ars_del_mes": "1"}).status_code == 404
    with pytest.raises(servicios.DatosInvalidos):
        servicios.corregir_gasto(api.session, viejo["codigo"], D("-1"))
    assert cantidad_de_filas(api, "2026-10") == filas


def test_a_pending_row_that_was_replaced_cannot_be_filled_in_anymore(api):
    pendiente = next(g for g in nuevo_gasto(api, "2027-02", "Luz", None)["gastos"])
    corregido = api.post(f"/costos-fijos/{pendiente['codigo']}/corregir", json={"monto_ars_del_mes": "50"}).json()
    assert corregido["pendientes"] == 0
    conflicto = api.post(f"/costos-fijos/{pendiente['codigo']}/monto", json={"monto_ars_del_mes": "1"})
    assert conflicto.status_code == 409 and "reemplazado" in conflicto.json()["detail"]
    assert api.get("/costos-fijos", params={"periodo": "2027-02"}).json() == corregido


def test_the_database_lets_a_row_be_replaced_by_at_most_one_row(api):
    viejo = api.session.scalar(select(GastoPeriodo).order_by(GastoPeriodo.id))
    campos = dict(periodo=viejo.periodo, concepto="x", fabrica_o_tienda="FABRICA", categoria="OTROS", reemplaza_a_id=viejo.id)
    api.session.add(GastoPeriodo(codigo="GF-8001", **campos))
    api.session.flush()
    with pytest.raises(IntegrityError):
        with api.session.begin_nested():
            api.session.add(GastoPeriodo(codigo="GF-8002", **campos))
            api.session.flush()


# --- S6: every reader ignores replaced rows ------------------------------------------------------------------

def test_panel_calidad_periods_and_export_data_ignore_replaced_rows(api):
    periodo = "2027-05"
    mes = nuevo_gasto(api, periodo, "Alquiler fábrica", "1000", categoria="ALQUILER")
    mes = nuevo_gasto(api, periodo, "Luz", None, categoria="SERVICIOS", ficticio=True)
    por_concepto = {g["concepto"]: g for g in mes["gastos"]}
    api.post(f"/costos-fijos/{por_concepto['Alquiler fábrica']['codigo']}/corregir", json={"monto_ars_del_mes": "1500"})
    api.post(f"/costos-fijos/{por_concepto['Luz']['codigo']}/corregir", json={"monto_ars_del_mes": "300", "ficticio": False})
    vigente = api.get("/costos-fijos", params={"periodo": periodo}).json()
    assert D(vigente["total_fabrica"]) == D("1800") and vigente["pendientes"] == 0 and vigente["incluye_ficticios"] is False
    panel = api.get("/panel/costos", params={"periodo": periodo}).json()["actual"]
    assert D(panel["fijos_fabrica"]) == D("1800") and panel["fijos_cargados"] is True
    hallazgos = [h for g in api.get("/calidad").json()["grupos"] if g["clave"] == "gastos_fijos" for h in g["hallazgos"]
                 if periodo in h["ruta"]]
    assert hallazgos == []  # the replaced pending / ficticio rows raise nothing
    periodos = api.get("/costos-fijos/periodos").json()["periodos"]
    assert periodos.count(periodo) == 1
    exportado = next(m for m in servicios.costos_fijos_de_todos_los_periodos(api.session) if m["periodo"] == periodo)
    assert len(exportado["gastos"]) == 2 and D(exportado["total"]) == D("1800")


# --- copy a month ----------------------------------------------------------------------------------------------

def test_copying_a_month_copies_only_the_current_rows_with_their_amounts(api):
    nuevo_gasto(api, "2027-03", "Alquiler", "1000", categoria="ALQUILER")
    nuevo_gasto(api, "2027-03", "Sueldo", "5000", categoria="SUELDOS", ficticio=True)
    mes = nuevo_gasto(api, "2027-03", "Luz", None, categoria="SERVICIOS")
    luz = next(g for g in mes["gastos"] if g["concepto"] == "Luz")
    api.post(f"/costos-fijos/{luz['codigo']}/corregir", json={"monto_ars_del_mes": "70"})
    origen = api.get("/costos-fijos", params={"periodo": "2027-03"}).json()
    respuesta = api.post("/costos-fijos/copiar", json={"desde": "2027-03", "hasta": "2027-04"})
    assert respuesta.status_code == 201, respuesta.text
    copia = respuesta.json()
    assert copia["periodo"] == "2027-04" and len(copia["gastos"]) == 3  # 3 current rows, not 4
    assert total(copia) == total(origen) == D("6070") and copia["incluye_ficticios"] is True
    assert all(g["reemplaza_a"] is None and "2027-03" in g["nota_fuente"] for g in copia["gastos"])
    assert {g["concepto"]: (g["monto_ars_del_mes"], g["ficticio"], g["categoria"], g["fabrica_o_tienda"]) for g in copia["gastos"]} == {
        g["concepto"]: (g["monto_ars_del_mes"], g["ficticio"], g["categoria"], g["fabrica_o_tienda"]) for g in origen["gastos"]}
    assert {g["codigo"] for g in copia["gastos"]}.isdisjoint(g["codigo"] for g in origen["gastos"])
    assert api.get("/costos-fijos", params={"periodo": "2027-03"}).json() == origen  # the source is untouched


def test_copying_without_amounts_leaves_every_row_pending(api):
    nuevo_gasto(api, "2027-03", "Alquiler", "1000", categoria="ALQUILER")
    nuevo_gasto(api, "2027-03", "Sueldo", "5000", categoria="SUELDOS")
    copia = api.post("/costos-fijos/copiar", json={"desde": "2027-03", "hasta": "2027-04", "con_montos": False}).json()
    assert len(copia["gastos"]) == 2 and copia["pendientes"] == 2 and total(copia) == 0
    assert {g["concepto"] for g in copia["gastos"]} == {"Alquiler", "Sueldo"}


def test_copying_refuses_a_target_with_rows_an_empty_source_and_bad_periods(api):
    nuevo_gasto(api, "2027-03", "Alquiler", "1000")
    nuevo_gasto(api, "2027-04", "Otro", "1")
    filas = cantidad_de_filas(api, "2027-04")
    conflicto = api.post("/costos-fijos/copiar", json={"desde": "2027-03", "hasta": "2027-04"})
    assert conflicto.status_code == 409 and "2027-04" in conflicto.json()["detail"]
    assert cantidad_de_filas(api, "2027-04") == filas
    vacio = api.post("/costos-fijos/copiar", json={"desde": "2030-01", "hasta": "2030-02"})
    assert vacio.status_code == 422 and "2030-01" in vacio.json()["detail"]
    assert api.get("/costos-fijos", params={"periodo": "2030-02"}).json()["gastos"] == []
    assert api.post("/costos-fijos/copiar", json={"desde": "2027-03", "hasta": "2027-03"}).status_code == 422
    assert api.post("/costos-fijos/copiar", json={"desde": "2027-13", "hasta": "2027-05"}).status_code == 422


# --- regressions proposed by the independent verifier ---------------------------------------------------------

def instantanea(api, *periodos):
    """Every row of the given months, including replaced ones, as (id, codigo, monto, reemplaza_a_id, nota_fuente)."""
    filas = api.session.execute(
        select(GastoPeriodo.id, GastoPeriodo.codigo, GastoPeriodo.monto_ars_del_mes, GastoPeriodo.reemplaza_a_id,
               GastoPeriodo.nota_fuente).where(GastoPeriodo.periodo.in_(periodos)).order_by(GastoPeriodo.id)).all()
    return [tuple(fila) for fila in filas]


def test_a_rejected_copy_leaves_both_months_byte_identical(api):
    nuevo_gasto(api, "2027-02", "Alquiler", "1000", categoria="ALQUILER")
    nuevo_gasto(api, "2027-03", "Luz", "70", categoria="SERVICIOS")
    mes = nuevo_gasto(api, "2027-03", "Gas", "30", categoria="SERVICIOS")
    gas = next(g for g in mes["gastos"] if g["concepto"] == "Gas")
    assert api.post(f"/costos-fijos/{gas['codigo']}/corregir", json={"monto_ars_del_mes": "35"}).status_code == 201
    antes = instantanea(api, "2027-02", "2027-03")
    vistas = [api.get("/costos-fijos", params={"periodo": p}).json() for p in ("2027-02", "2027-03")]
    rechazada = api.post("/costos-fijos/copiar", json={"desde": "2027-02", "hasta": "2027-03"})
    assert rechazada.status_code == 409
    assert rechazada.json() == {"detail": "El mes 2027-03 ya tiene gastos: no se copia encima."}
    assert instantanea(api, "2027-02", "2027-03") == antes
    assert [api.get("/costos-fijos", params={"periodo": p}).json() for p in ("2027-02", "2027-03")] == vistas


def test_a_copy_made_after_a_correction_carries_only_the_corrected_amount(api):
    nuevo_gasto(api, "2027-03", "Alquiler", "1000", categoria="ALQUILER")
    mes = nuevo_gasto(api, "2027-03", "Luz", "70", categoria="SERVICIOS")
    luz = next(g for g in mes["gastos"] if g["concepto"] == "Luz")
    assert api.post(f"/costos-fijos/{luz['codigo']}/corregir", json={"monto_ars_del_mes": "90"}).status_code == 201
    origen = api.get("/costos-fijos", params={"periodo": "2027-03"}).json()
    copia = api.post("/costos-fijos/copiar", json={"desde": "2027-03", "hasta": "2027-04"}).json()
    assert total(copia) == total(origen) == D("1090")
    assert len(copia["gastos"]) == len(origen["gastos"]) == 2
    assert {g["concepto"]: D(g["monto_ars_del_mes"]) for g in copia["gastos"]} == {"Alquiler": D("1000"), "Luz": D("90")}
    assert all(g["reemplaza_a"] is None for g in copia["gastos"])
    assert cantidad_de_filas(api, "2027-04") == 2  # the replaced 70 was not copied as a hidden row either
    assert api.session.scalar(
        select(func.count()).select_from(GastoPeriodo).where(GastoPeriodo.periodo == "2027-04", GastoPeriodo.reemplaza_a_id.is_not(None))) == 0


def test_the_sheets_export_lists_no_replaced_row(api):
    mes = nuevo_gasto(api, "2027-05", "Alquiler", "1000", categoria="ALQUILER")
    alquiler = next(g for g in mes["gastos"] if g["concepto"] == "Alquiler")
    corregido = api.post(f"/costos-fijos/{alquiler['codigo']}/corregir", json={"monto_ars_del_mes": "1200"}).json()
    nuevo = next(g for g in corregido["gastos"] if g["reemplaza_a"] == alquiler["codigo"])
    exportado = servicios.costos_fijos_de_todos_los_periodos(api.session)
    codigos = [g["codigo"] for m in exportado for g in m["gastos"]]
    assert alquiler["codigo"] not in codigos and nuevo["codigo"] in codigos
    assert len(codigos) == len(set(codigos))
    mayo = next(m for m in exportado if m["periodo"] == "2027-05")
    assert len(mayo["gastos"]) == 1 and D(mayo["total"]) == D("1200")
