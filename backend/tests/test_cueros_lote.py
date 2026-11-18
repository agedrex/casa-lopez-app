"""Leather summary of a lot (GET /ordenes/{codigo}/cuero) against disposable PostgreSQL; skipped without TEST_DATABASE_URL."""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

# MOD-0001 uses 0.25 m2 of leather per unit (seed): 4 units need 1 m2.


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    role = {"value": "admin"}
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-lote-cuero", role=role["value"]))
    try:
        with TestClient(app) as client:
            yield client, role
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def comprar(client, m2, material="MAT-CU01", color=None):
    respuesta = client.post("/cueros", json={
        "origen": "COMPRA", "material": material, "color": color, "m2_iniciales": m2,
        "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def producto(client, cuero="MAT-CU01", color=None, modelo="MOD-0001"):
    respuesta = client.post("/productos", json={"modelo": modelo, "cuero": cuero, "color": color,
                                               "quien_lo_confecciona": "INTERNA"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def lote(client, items):
    respuesta = client.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": "2026-10-02",
        "items": [{"producto": p, "cantidad": c} for p, c in items]})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"], [i["codigo"] for i in respuesta.json()["items"]]


def test_products_sharing_a_leather_are_added_up_and_checked_against_one_stock(api):
    client, role = api
    comprar(client, "1.5")
    a, b = producto(client), producto(client, modelo="MOD-0031")  # same leather use (0.25 m2), another model (S5)
    codigo, _ = lote(client, [(a, "4"), (b, "4")])
    # Each product alone fits in 1.5 m2 (needs 1), but together they need 2.
    for p in (a, b):
        assert client.get("/cueros/alcanza", params={"producto": p, "cantidad": "4"}).json()["alcanza"] is True
    role["value"] = "taller"
    respuesta = client.get(f"/ordenes/{codigo}/cuero")
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["lote"] == codigo and datos["sin_consumo"] == []
    assert len(datos["cueros"]) == 1
    grupo = datos["cueros"][0]
    assert grupo["material"] == "MAT-CU01" and grupo["color"] is None and grupo["productos"] == [a, b]
    assert D(grupo["necesario"]) == 2 and D(grupo["por_cortar"]) == 2 and D(grupo["ya_cortado"]) == 0
    assert D(grupo["disponible"]) == D("1.5") and grupo["alcanza"] is False
    assert D(grupo["faltante"]) == D("0.5") and D(grupo["sobrante"]) == 0
    # The same stock as GET /cueros/alcanza.
    assert D(grupo["disponible"]) == D(client.get("/cueros/alcanza", params={"producto": a, "cantidad": "4"}).json()["disponible"])
    assert not any("ars" in clave or "precio" in clave for clave in grupo)


def test_leftover_is_reported_when_stock_covers_the_lot(api):
    client, _ = api
    comprar(client, "3")
    codigo, _ = lote(client, [(producto(client), "4")])
    grupo = client.get(f"/ordenes/{codigo}/cuero").json()["cueros"][0]
    assert grupo["alcanza"] is True and D(grupo["faltante"]) == 0 and D(grupo["sobrante"]) == 2


def test_leather_without_stock_is_still_listed_and_split_by_color_and_material(api):
    client, _ = api
    assert client.post("/colores", json={"nombre": "Azul"}).status_code == 201
    comprar(client, "5", color="Azul")
    azul = producto(client, color="Azul")
    sin_color = producto(client)
    carpincho = producto(client, cuero="MAT-CU02")
    codigo, _ = lote(client, [(azul, "4"), (sin_color, "4"), (carpincho, "8")])
    grupos = {(g["material"], g["color"]): g for g in client.get(f"/ordenes/{codigo}/cuero").json()["cueros"]}
    assert set(grupos) == {("MAT-CU01", "Azul"), ("MAT-CU01", None), ("MAT-CU02", None)}
    assert grupos[("MAT-CU01", "Azul")]["alcanza"] is True
    vacio = grupos[("MAT-CU01", None)]
    assert D(vacio["disponible"]) == 0 and D(vacio["faltante"]) == 1 and vacio["alcanza"] is False
    assert D(grupos[("MAT-CU02", None)]["necesario"]) == 2


def test_leather_already_cut_for_the_lot_is_not_counted_twice(api):
    client, _ = api
    pieza = comprar(client, "3")
    p = producto(client)
    codigo, items = lote(client, [(p, "4")])
    corte = client.post(f"/cueros/{pieza}/cortes", json={"m2": "0.6", "orden_item": items[0], "fecha": "2026-10-02"})
    assert corte.status_code == 201, corte.text
    grupo = client.get(f"/ordenes/{codigo}/cuero").json()["cueros"][0]
    assert D(grupo["necesario"]) == 1 and D(grupo["ya_cortado"]) == D("0.6") and D(grupo["por_cortar"]) == D("0.4")
    assert D(grupo["disponible"]) == D("2.4") and grupo["alcanza"] is True
    # Cutting more than the item needs never makes the amount left to cut negative.
    assert client.post(f"/cueros/{pieza}/cortes", json={"m2": "1", "orden_item": items[0]}).status_code == 201
    grupo = client.get(f"/ordenes/{codigo}/cuero").json()["cueros"][0]
    assert D(grupo["ya_cortado"]) == 1 and D(grupo["por_cortar"]) == 0


def test_product_without_consumption_is_listed_apart_and_unknown_lot_is_404(api):
    client, role = api
    sin_modelo = client.post("/productos", json={"nombre_propio": "Kit regalo", "es_kit": True})
    assert sin_modelo.status_code == 201, sin_modelo.text
    codigo, _ = lote(client, [(sin_modelo.json()["codigo"], "2")])
    datos = client.get(f"/ordenes/{codigo}/cuero").json()
    assert datos["cueros"] == []
    assert datos["sin_consumo"] == [{"producto": sin_modelo.json()["codigo"], "producto_nombre": "Kit regalo"}]
    assert client.get("/ordenes/LOT-9999/cuero").status_code == 404
    role["value"] = "gerente"
    assert client.get(f"/ordenes/{codigo}/cuero").status_code == 403


def test_availability_endpoint_keeps_its_previous_behavior(api):
    client, _ = api
    p = producto(client)
    assert D(client.get("/cueros/alcanza", params={"producto": p, "cantidad": "4"}).json()["disponible"]) == 0
    pieza = comprar(client, "0.5")
    datos = client.get("/cueros/alcanza", params={"producto": p, "cantidad": "4"}).json()
    assert D(datos["necesario"]) == 1 and D(datos["faltante"]) == D("0.5") and datos["alcanza"] is False
    assert [x["codigo"] for x in datos["piezas"]] == [pieza]
