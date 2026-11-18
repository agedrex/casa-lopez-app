"""The taller moves a lot forward one state at a time (S11) and the history says who and when (S12).

HTTP flows against the disposable local PostgreSQL (skipped without TEST_DATABASE_URL). The role gates themselves are in
test_roles.py; here the behaviour behind them.
"""

from datetime import date

from backend import lote_estados
from backend.auth import Usuario, get_verifier
from backend.main import app
from test_api_integration import api, producto  # noqa: F401  (fixture and helper)
from test_fabricacion import lote_nuevo


def como(rol, usuario="usuario-taller"):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id=usuario, role=rol))


def lote(api, con_cuero_cortado=True):
    """LOT-0001 with one line; its leather is already cut (the taller cannot reach CORTADA otherwise, S3 of mejoras-qa-staging)."""
    creado = lote_nuevo(api, producto(api)["codigo"])
    if con_cuero_cortado:
        pieza = api.post("/cueros", json={
            "origen": "COMPRA", "material": "MAT-CU01", "color": None, "m2_iniciales": "5",
            "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS"}).json()["codigo"]
        corte = api.post(f"/cueros/{pieza}/cortes", json={"m2": "1", "orden_item": creado["items"][0]["codigo"], "fecha": "2026-10-06"})
        assert corte.status_code == 201, corte.text
    return "/ordenes/LOT-0001"


def test_taller_advances_one_state_at_a_time_with_who_and_when(api, monkeypatch):
    ruta = lote(api)
    monkeypatch.setattr(lote_estados, "hoy_de_buenos_aires", lambda: date(2026, 11, 18))
    como("taller")
    for siguiente in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        respuesta = api.post(f"{ruta}/avanzar")
        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["estado"] == siguiente
    historial = api.get(ruta).json()["estados"]
    assert [e["estado"] for e in historial] == ["PLANIFICADA", "EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"]
    assert historial[0]["cambiado_por"] is None  # the creation row has no author
    assert [(e["fecha"], e["cambiado_por"]) for e in historial[1:]] == [("2026-11-18", "usuario-taller")] * 4
    assert all(e["registrado_en"] for e in historial)


def test_taller_cannot_close_the_lot_nor_skip_states(api):
    ruta = lote(api)
    como("taller")
    # Only the next state exists for the taller: the old route, where any state can be chosen, stays admin only.
    assert api.post(f"{ruta}/estado", json={"estado": "LISTA", "fecha": "2026-11-18"}).status_code == 403
    assert api.get(ruta).json()["estado"] == "PLANIFICADA"
    for _ in range(4):
        assert api.post(f"{ruta}/avanzar").status_code == 201
    cierre = api.post(f"{ruta}/avanzar")  # LISTA -> CERRADA needs the delivery date: the admin closes
    assert cierre.status_code == 409 and "administrador" in cierre.json()["detail"]
    detalle = api.get(ruta).json()
    assert detalle["estado"] == "LISTA" and len(detalle["estados"]) == 5  # the refusal left no history row


def test_advance_refuses_a_closed_lot_and_an_unknown_one(api):
    ruta = lote(api)
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        assert api.post(f"{ruta}/estado", json={"estado": estado, "fecha": "2026-10-06"}).status_code == 201
    assert api.post(f"{ruta}/estado", json={"estado": "CERRADA", "fecha": "2026-10-20", "fecha_de_entrega": "2026-10-19"}).status_code == 201
    como("taller")
    assert api.post(f"{ruta}/avanzar").status_code == 409
    assert api.post("/ordenes/LOT-9999/avanzar").status_code == 404
    assert len(api.get(ruta).json()["estados"]) == 6


def test_the_state_change_of_the_admin_records_the_logged_in_user_and_keeps_its_rules(api):
    ruta = lote(api)  # the fixture's admin is "usuario-de-prueba"
    avance = api.post(f"{ruta}/estado", json={"estado": "EN_CORTE", "fecha": "2026-10-06", "quien": "PER-0002"})
    assert avance.status_code == 201, avance.text
    ultimo = avance.json()["estados"][-1]
    assert (ultimo["quien"], ultimo["cambiado_por"]) == ("PER-0002", "usuario-de-prueba")
    for estado in ("CORTADA", "EN_CONFECCION", "LISTA"):
        assert api.post(f"{ruta}/estado", json={"estado": estado, "fecha": "2026-10-07"}).status_code == 201
    sin_entrega = api.post(f"{ruta}/estado", json={"estado": "CERRADA", "fecha": "2026-10-20"})
    assert sin_entrega.status_code == 422 and "entrega" in sin_entrega.json()["detail"]


def test_the_taller_still_cannot_write_anything_else_of_a_lot(api):
    ruta = lote(api)
    como("taller")
    assert api.post("/ordenes", json={"donde_se_hace": "INTERNA", "items": []}).status_code == 403
    assert api.post(f"{ruta}/items", json={"producto": "PRD-0001", "cantidad": "1"}).status_code == 403
    assert api.post(f"{ruta}/estado", json={"estado": "EN_CORTE", "fecha": "2026-11-18"}).status_code == 403
    assert api.post(f"{ruta}/items/LIT-0001/precios", json={"pagado": "1"}).status_code == 200  # the voice flow, unchanged
    como("gerente")
    assert api.post(f"{ruta}/avanzar").status_code == 403
    assert api.get(ruta).status_code == 403
