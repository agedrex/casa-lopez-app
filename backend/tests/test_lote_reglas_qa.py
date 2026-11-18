"""Reglas de lotes que encontró el QA de staging (S3 y S4 de odd/tasks/mejoras-qa-staging.md).

Contra PostgreSQL descartable; se saltea sin TEST_DATABASE_URL. Lo que ya cubrían taller-estados y lote-editar-items
(el taller avanza de a un estado, un lote cerrado no cambia la cantidad ni quita renglones) vive en test_lote_estados.py
y test_lote_items.py; acá está lo nuevo.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

CICLO = ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA")


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    rol = {"value": "admin"}
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="qa-lote", role=rol["value"]))
    try:
        with TestClient(app) as client:
            client.rol = rol
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def producto(client, **cambios):
    cuerpo = {"modelo": "MOD-0001", "cuero": "MAT-CU01", "color": None, "quien_lo_confecciona": "INTERNA", **cambios}
    respuesta = client.post("/productos", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def lote(client, items, **cambios):
    respuesta = client.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": "2026-10-02",
        "items": [{"producto": p, "cantidad": c} for p, c in items], **cambios})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"], [i["codigo"] for i in respuesta.json()["items"]]


def estado(client, codigo, nuevo, **cuerpo):
    return client.post(f"/ordenes/{codigo}/estado", json={"estado": nuevo, "fecha": "2026-10-10", **cuerpo})


def cortar(client, item, m2="0.5"):
    rol, client.rol["value"] = client.rol["value"], "admin"  # buying the hide is the admin's; the cut itself is the taller's
    pieza = client.post("/cueros", json={
        "origen": "COMPRA", "material": "MAT-CU01", "color": None, "m2_iniciales": "5",
        "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS"})
    assert pieza.status_code == 201, pieza.text
    corte = client.post(f"/cueros/{pieza.json()['codigo']}/cortes", json={"m2": m2, "orden_item": item, "fecha": "2026-10-03"})
    assert corte.status_code == 201, corte.text
    client.rol["value"] = rol


# --- S3: el admin no salta estados --------------------------------------------------------------------------------

@pytest.mark.parametrize("destino", ["CORTADA", "EN_CONFECCION", "LISTA", "CERRADA"])
def test_the_admin_cannot_skip_ahead_from_planificada(api, destino):
    codigo, _ = lote(api, [(producto(api), "2")])
    respuesta = estado(api, codigo, destino, fecha_de_entrega="2026-10-20")
    assert respuesta.status_code == 409, respuesta.text
    detalle = respuesta.json()["detail"]
    assert "En corte" in detalle and "Planificada" in detalle and "EN_CORTE" not in detalle
    antes = api.get(f"/ordenes/{codigo}").json()
    assert antes["estado"] == "PLANIFICADA" and len(antes["estados"]) == 1  # la negativa no dejó historia


def test_the_admin_cannot_go_back_and_walks_the_whole_cycle_one_state_at_a_time(api):
    codigo, _ = lote(api, [(producto(api), "2")])
    for nuevo in CICLO[:2]:
        assert estado(api, codigo, nuevo).status_code == 201
    atras = estado(api, codigo, "EN_CORTE")
    assert atras.status_code == 409 and "En confección" in atras.json()["detail"]
    for nuevo in CICLO[2:-1]:
        assert estado(api, codigo, nuevo).status_code == 201
    cierre = estado(api, codigo, "CERRADA", fecha_de_entrega="2026-10-20")
    assert cierre.status_code == 201 and cierre.json()["estado"] == "CERRADA"
    assert [e["estado"] for e in cierre.json()["estados"]] == ["PLANIFICADA", *CICLO]


# --- S3: el taller no pasa a Cortada / Lista sin cuero cortado ---------------------------------------------------

def test_taller_cannot_mark_a_lot_cut_or_ready_until_its_leather_was_cut(api):
    codigo, (item,) = lote(api, [(producto(api), "4")])
    api.rol["value"] = "taller"
    assert api.post(f"/ordenes/{codigo}/avanzar").status_code == 201  # EN_CORTE: se puede empezar a cortar
    bloqueado = api.post(f"/ordenes/{codigo}/avanzar")
    assert bloqueado.status_code == 409, bloqueado.text
    assert "cuero" in bloqueado.json()["detail"] and "cortado" in bloqueado.json()["detail"]
    assert api.get(f"/ordenes/{codigo}").json()["estado"] == "EN_CORTE"
    assert len(api.get(f"/ordenes/{codigo}").json()["estados"]) == 2
    cortar(api, item)
    for siguiente in ("CORTADA", "EN_CONFECCION", "LISTA"):
        respuesta = api.post(f"/ordenes/{codigo}/avanzar")
        assert respuesta.status_code == 201 and respuesta.json()["estado"] == siguiente, respuesta.text


def test_every_line_with_leather_needs_its_cut_and_a_line_added_later_blocks_the_ready_state(api):
    codigo, (primero,) = lote(api, [(producto(api), "4")])
    cortar(api, primero)
    for nuevo in ("EN_CORTE", "CORTADA", "EN_CONFECCION"):
        assert estado(api, codigo, nuevo).status_code == 201
    nuevo_item = api.post(f"/ordenes/{codigo}/items", json={"producto": producto(api), "cantidad": "1"})
    assert nuevo_item.status_code == 201
    api.rol["value"] = "taller"
    sin_cortar = api.post(f"/ordenes/{codigo}/avanzar")
    assert sin_cortar.status_code == 409 and "cuero" in sin_cortar.json()["detail"]
    cortar(api, nuevo_item.json()["items"][-1]["codigo"])
    assert api.post(f"/ordenes/{codigo}/avanzar").json()["estado"] == "LISTA"


def test_a_removed_line_and_a_product_without_leather_do_not_ask_for_a_cut(api):
    kit = api.post("/productos", json={"nombre_propio": "Kit regalo", "es_kit": True})
    assert kit.status_code == 201, kit.text
    codigo, (item_kit, item_cuero) = lote(api, [(kit.json()["codigo"], "1"), (producto(api), "2")])
    assert api.delete(f"/ordenes/{codigo}/items/{item_cuero}").status_code == 200
    api.rol["value"] = "taller"
    for siguiente in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        assert api.post(f"/ordenes/{codigo}/avanzar").json()["estado"] == siguiente


def test_the_untouched_rules_still_hold(api):
    """PRESERVE: repetir el estado actual sigue siendo 409 y cerrar sin entrega sigue siendo 422."""
    codigo, _ = lote(api, [(producto(api), "2")])
    assert estado(api, codigo, "PLANIFICADA").status_code == 409
    for nuevo in CICLO[:-1]:
        assert estado(api, codigo, nuevo).status_code == 201
    sin_entrega = estado(api, codigo, "CERRADA")
    assert sin_entrega.status_code == 422 and "entrega" in sin_entrega.json()["detail"]
