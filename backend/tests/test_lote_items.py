"""Admin edits a lot's lines: change a quantity, remove a line (S6, S7 of odd/tasks/lanzamiento-listo.md).

Against disposable PostgreSQL; skipped without TEST_DATABASE_URL. The role gates live in test_roles.py (ACCESO).
"""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

SIN_PERMISO = {"detail": "No tenés permiso para esta acción."}


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    role = {"value": "admin"}
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="user-admin-1", role=role["value"]))
    try:
        with TestClient(app) as client:
            yield client, role, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


# Seed models that use 0.25 m2 of leather per unit, like MOD-0001: a test gets a new product by taking the next one
# (model + leather + colour must be unique, S5) and the leather it needs stays the same, with no colour.
MODELOS_DE_CUERO_025 = ("MOD-0001", "MOD-0031", "MOD-0074", "MOD-0125", "MOD-0222")


def producto(client):
    usados = client.get("/productos", params={"limit": 500}).json()
    modelo = next(m for m in MODELOS_DE_CUERO_025 if m not in {p["modelo"] for p in usados})
    respuesta = client.post("/productos", json={"modelo": modelo, "cuero": "MAT-CU01", "color": None,
                                               "quien_lo_confecciona": "INTERNA"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def lote(client, items, **cambios):
    respuesta = client.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": "2026-10-02",
        "items": [{"producto": p, "cantidad": c} for p, c in items], **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"], [i["codigo"] for i in respuesta.json()["items"]]


def cerrar(client, codigo):
    respuesta = client.post(f"/ordenes/{codigo}/estado", json={
        "estado": "CERRADA", "fecha": "2026-10-20", "fecha_de_entrega": "2026-10-20"})
    assert respuesta.status_code == 201, respuesta.text


# --- S7: change the quantity ------------------------------------------------------------------------------------

def test_admin_changes_the_quantity_of_a_line_and_the_change_is_logged_on_the_line(api):
    client, _, _ = api
    p = producto(client)
    codigo, (item,) = lote(client, [(p, "10")])
    respuesta = client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "4"})
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert [(i["codigo"], D(i["cantidad"])) for i in datos["items"]] == [(item, D("4"))]
    assert D(datos["unidades"]) == 4 and datos["productos"] == 1
    # The previous value is not lost: it stays in the line's note with the date and who changed it.
    assert "10 → 4" in datos["items"][0]["nota"] and "user-admin-1" in datos["items"][0]["nota"]
    # Repeating the same quantity is a conflict, so a double click leaves a single log line.
    assert client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "4"}).status_code == 409
    assert client.get(f"/ordenes/{codigo}").json()["items"][0]["nota"].count("10 → 4") == 1
    # A second, different change adds a second log line and keeps the first.
    nota = client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "6.5"}).json()["items"][0]["nota"]
    assert "10 → 4" in nota and "4 → 6.5" in nota


@pytest.mark.parametrize("cantidad", ["0", "-1", "abc", None])
def test_the_quantity_must_be_greater_than_zero_and_a_rejected_one_changes_nothing(api, cantidad):
    client, _, _ = api
    codigo, (item,) = lote(client, [(producto(client), "10")])
    assert client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": cantidad}).status_code == 422
    assert client.put(f"/ordenes/{codigo}/items/{item}", json={}).status_code == 422
    assert client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "1", "producto": "X"}).status_code == 422
    linea = client.get(f"/ordenes/{codigo}").json()["items"][0]
    assert D(linea["cantidad"]) == 10 and linea["nota"] is None


def test_the_same_product_can_be_in_a_lot_several_times_with_any_quantity_and_each_line_is_edited_alone(api):
    client, _, _ = api
    a, b = producto(client), producto(client)
    codigo, items = lote(client, [(a, "3"), (a, "5"), (b, "3")])  # S6: never blocked
    assert len(items) == 3
    assert client.post(f"/ordenes/{codigo}/items", json={"producto": a, "cantidad": "1"}).status_code == 201
    cambiado = client.put(f"/ordenes/{codigo}/items/{items[1]}", json={"cantidad": "9"}).json()
    assert [D(i["cantidad"]) for i in cambiado["items"]] == [D("3"), D("9"), D("3"), D("1")]
    assert [i["nota"] is None for i in cambiado["items"]] == [True, False, True, True]
    # Editing to the quantity another line of the same product already has is fine (no uniqueness anywhere).
    assert client.put(f"/ordenes/{codigo}/items/{items[1]}", json={"cantidad": "3"}).status_code == 200


def test_a_closed_lot_cannot_be_edited_but_every_open_state_can(api):
    client, _, _ = api
    codigo, (item, otro) = lote(client, [(producto(client), "10"), (producto(client), "2")])
    for nueva, estado in enumerate(("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"), start=1):
        assert client.post(f"/ordenes/{codigo}/estado", json={"estado": estado, "fecha": "2026-10-10"}).status_code == 201
        assert client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": str(nueva)}).status_code == 200, estado
    cerrar(client, codigo)
    antes = client.get(f"/ordenes/{codigo}").json()
    for respuesta in (client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "1"}),
                      client.delete(f"/ordenes/{codigo}/items/{otro}")):
        assert respuesta.status_code == 409 and "cerrado" in respuesta.json()["detail"]
    assert client.get(f"/ordenes/{codigo}").json() == antes


def test_edit_and_remove_answer_404_for_an_unknown_lot_or_a_line_of_another_lot(api):
    client, _, _ = api
    p = producto(client)
    uno, (item_uno,) = lote(client, [(p, "1")])
    dos, (item_dos,) = lote(client, [(p, "1")])
    for metodo, cuerpo in (("put", {"json": {"cantidad": "2"}}), ("delete", {})):
        llamar = getattr(client, metodo)
        assert llamar("/ordenes/LOT-9999/items/" + item_uno, **cuerpo).status_code == 404
        assert llamar(f"/ordenes/{uno}/items/LIT-9999", **cuerpo).status_code == 404
        assert llamar(f"/ordenes/{uno}/items/{item_dos}", **cuerpo).status_code == 404
    assert D(client.get(f"/ordenes/{dos}").json()["items"][0]["cantidad"]) == 1


# --- S7: remove a line ------------------------------------------------------------------------------------------

def test_removing_a_line_keeps_the_row_logs_it_and_takes_it_out_of_the_lot(api):
    client, _, sesion = api
    a, b = producto(client), producto(client)
    codigo, (uno, dos) = lote(client, [(a, "4"), (b, "6")])
    respuesta = client.delete(f"/ordenes/{codigo}/items/{uno}")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert [i["codigo"] for i in datos["items"]] == [dos]
    assert datos["productos"] == 1 and D(datos["unidades"]) == 6
    assert not any("Falta la cantidad" in aviso for aviso in datos["avisos"])
    assert [(q["codigo"], q["producto"]) for q in datos["quitados"]] == [(uno, a)]
    assert "4 → 0" in datos["quitados"][0]["nota"] and "user-admin-1" in datos["quitados"][0]["nota"]
    # AGENTS rule 11: nothing is deleted. The row is still there, at zero, with its history.
    fila = sesion.execute(text("select cantidad, nota from costos.orden_item where codigo = :c"), {"c": uno}).one()
    assert fila.cantidad == 0 and "4 → 0" in fila.nota
    # Already removed: neither removed nor edited again, and the log is not duplicated.
    assert client.delete(f"/ordenes/{codigo}/items/{uno}").status_code == 409
    assert client.put(f"/ordenes/{codigo}/items/{uno}", json={"cantidad": "3"}).status_code == 409
    assert client.get(f"/ordenes/{codigo}").json()["quitados"][0]["nota"].count("4 → 0") == 1
    # Adding the same product again is a new line (it never reuses the removed one).
    nuevo = client.post(f"/ordenes/{codigo}/items", json={"producto": a, "cantidad": "2"}).json()
    assert [i["codigo"] for i in nuevo["items"]] == [dos, "LIT-0003"] and len(nuevo["quitados"]) == 1


def test_a_removed_line_no_longer_counts_anywhere_else(api):
    client, role, _ = api
    a = producto(client)
    codigo, (uno,) = lote(client, [(a, "4")], estado="EN_CORTE")  # a PLANIFICADA lot does not count as produced
    antes = {f["producto"]: f for f in client.get("/ordenes/unidades-por-producto").json()["productos"]}
    assert D(antes[a]["unidades"]) == 4 and antes[a]["lotes"] == 1
    assert client.delete(f"/ordenes/{codigo}/items/{uno}").status_code == 200
    despues = {f["producto"] for f in client.get("/ordenes/unidades-por-producto").json()["productos"]}
    assert a not in despues
    [en_lista] = [o for o in client.get("/ordenes").json() if o["codigo"] == codigo]
    assert en_lista["productos"] == 0 and D(en_lista["unidades"]) == 0
    role["value"] = "taller"  # the leather summary the taller reads ignores it too
    cuero = client.get(f"/ordenes/{codigo}/cuero").json()
    assert cuero["cueros"] == [] and cuero["sin_consumo"] == []


def test_a_line_that_already_has_leather_cut_for_it_cannot_be_removed_but_its_quantity_can_change(api):
    client, _, _ = api
    pieza = client.post("/cueros", json={
        "origen": "COMPRA", "material": "MAT-CU01", "color": None, "m2_iniciales": "2",
        "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS"}).json()["codigo"]
    codigo, (item,) = lote(client, [(producto(client), "4")])
    assert client.post(f"/cueros/{pieza}/cortes", json={"m2": "0.5", "orden_item": item, "fecha": "2026-10-03"}).status_code == 201
    respuesta = client.delete(f"/ordenes/{codigo}/items/{item}")
    assert respuesta.status_code == 409 and "corte" in respuesta.json()["detail"]
    assert client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "3"}).status_code == 200
    assert [i["codigo"] for i in client.get(f"/ordenes/{codigo}").json()["items"]] == [item]


def test_leather_cannot_be_cut_against_a_removed_line(api):
    client, _, _ = api
    pieza = client.post("/cueros", json={
        "origen": "COMPRA", "material": "MAT-CU01", "color": None, "m2_iniciales": "2",
        "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS"}).json()["codigo"]
    codigo, (item,) = lote(client, [(producto(client), "4")])
    assert client.delete(f"/ordenes/{codigo}/items/{item}").status_code == 200
    assert client.post(f"/cueros/{pieza}/cortes", json={"m2": "0.5", "orden_item": item, "fecha": "2026-10-03"}).status_code == 422


# --- Roles ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["taller", "gerente"])
def test_only_the_admin_edits_or_removes_lines(api, role):
    client, rol, _ = api
    codigo, (item,) = lote(client, [(producto(client), "4")])
    rol["value"] = role
    for respuesta in (client.put(f"/ordenes/{codigo}/items/{item}", json={"cantidad": "1"}),
                      client.delete(f"/ordenes/{codigo}/items/{item}")):
        assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO
    rol["value"] = "admin"
    linea = client.get(f"/ordenes/{codigo}").json()["items"][0]
    assert D(linea["cantidad"]) == 4 and linea["nota"] is None


# --- PRESERVE: what shares the code I touched -------------------------------------------------------------------

def test_a_line_created_with_zero_units_still_shows_up_with_its_warning_and_the_price_route_still_works(api):
    client, rol, _ = api
    codigo, (cero, normal) = lote(client, [(producto(client), "0"), (producto(client), "2")])
    detalle = client.get(f"/ordenes/{codigo}").json()
    assert [i["codigo"] for i in detalle["items"]] == [cero, normal] and detalle["quitados"] == []
    assert "Falta la cantidad" in detalle["items"][0]["avisos"]
    rol["value"] = "taller"
    precio = client.post(f"/ordenes/{codigo}/items/{normal}/precios", json={"pagado": "100"})
    assert precio.status_code == 200 and D(precio.json()["items"][1]["pagado"]) == 100


def test_a_removed_line_is_left_out_of_the_lot_consumption(api):
    client, _, _ = api
    a, b = producto(client), producto(client)
    codigo, (uno, dos) = lote(client, [(a, "4"), (b, "6")])
    assert len(client.get(f"/ordenes/{codigo}/consumo").json()["productos"]) == 2
    assert client.delete(f"/ordenes/{codigo}/items/{uno}").status_code == 200
    consumo = client.get(f"/ordenes/{codigo}/consumo").json()
    assert [fila["item"] for fila in consumo["productos"]] == [dos]
