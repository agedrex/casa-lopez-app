"""Leather HTTP loop against disposable PostgreSQL; skipped without TEST_DATABASE_URL."""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    role = {"value": "cotizador"}
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-cueros", role=role["value"]))
    try:
        with TestClient(app) as client:
            yield client, role
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def comprar(client, **cambios):
    cuerpo = {"origen": "COMPRA", "material": "MAT-CU01", "m2_iniciales": "10",
              "fecha_de_compra": "2026-10-01", "precio_pagado_por_m2": "20", "moneda": "ARS", **cambios}
    respuesta = client.post("/cueros", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def lote_para(client, cuero="MAT-CU01", color=None):
    producto = client.post("/productos", json={"modelo": "MOD-0001", "cuero": cuero, "color": color,
                                            "quien_lo_confecciona": "INTERNA"})
    assert producto.status_code == 201, producto.text
    orden = client.post("/ordenes", json={"donde_se_hace": "INTERNA", "fecha_de_envio": "2026-10-02",
                                         "items": [{"producto": producto.json()["codigo"], "cantidad": "4"}]})
    assert orden.status_code == 201, orden.text
    return producto.json()["codigo"], orden.json()["items"][0]["codigo"]


def test_purchase_cut_and_irrecoverable_remainder_are_append_only(api):
    client, role = api
    piel = comprar(client)
    codigo = piel["codigo"]
    assert codigo.startswith("PZC-") and piel["estado"] == "ENTERA"
    assert D(piel["natural"]) == 1 and D(piel["disponible"]) == 9
    assert [(m["tipo"], D(m["m2"]), m["fecha"]) for m in piel["movimientos"]] == [
        ("DESPERDICIO", D("-1"), "2026-10-01")]
    producto, item = lote_para(client)
    role["value"] = "corte"
    assert client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": "MAT-CU01",
                                         "m2_iniciales": "2"}).status_code == 403
    assert client.post(f"/cueros/{codigo}/cortes", json={"m2": "10", "orden_item": item}).status_code == 422
    assert client.post(f"/cueros/{codigo}/cortes", json={"m2": "1", "orden_item": "LIT-9999"}).status_code == 422
    cortada = client.post(f"/cueros/{codigo}/cortes", json={"m2": "7.65", "orden_item": item,
                                                       "fecha": "2026-10-02", "unidades": "4"})
    assert cortada.status_code == 201, cortada.text
    assert cortada.json()["estado"] == "EN_USO" and D(cortada.json()["disponible"]) == D("1.35")
    resumen = client.get("/cueros").json()[0]
    assert (D(resumen["comprado"]), D(resumen["natural"]), D(resumen["cuero_total_real"])) == (10, 1, 9)
    assert D(resumen["cortado"]) == D("7.65") and D(resumen["costo_desperdicio_ars"]) == 20
    assert client.get("/cueros/alcanza", params={"producto": producto, "cantidad": "4"}).json()["alcanza"] is True
    reutilizable = client.post(f"/cueros/{codigo}/sobrante", json={"decision": "REUTILIZABLE", "fecha": "2026-10-02"})
    assert reutilizable.status_code == 200 and reutilizable.json()["estado"] == "RETAZO"
    assert D(reutilizable.json()["disponible"]) == D("1.35")
    cerrado = client.post(f"/cueros/{codigo}/sobrante", json={"decision": "IRRECUPERABLE", "fecha": "2026-10-03"})
    assert cerrado.status_code == 200, cerrado.text
    assert cerrado.json()["estado"] == "CERRADA" and D(cerrado.json()["disponible"]) == 0
    assert [m["tipo"] for m in cerrado.json()["movimientos"]] == ["DESPERDICIO", "CORTE", "DESPERDICIO"]
    resumen = client.get("/cueros").json()[0]
    assert D(resumen["irrecuperable"]) == D("1.35")
    assert D(resumen["porcentaje_desperdicio_neto"]) == D("23.5")
    assert D(resumen["costo_desperdicio_ars"]) == D("47")
    assert resumen["umbral_medido"]["casos"] == 1
    assert D(resumen["umbral_medido"]["promedio_m2"]) == D("1.35")
    assert D(resumen["umbral_medido"]["promedio_pct_comprado"]) == D("13.5")
    assert client.post(f"/cueros/{codigo}/cortes", json={"m2": "0.1", "orden_item": item}).status_code == 409


def test_existing_remainder_and_reusable_decision_have_no_natural_waste(api):
    client, _ = api
    respuesta = client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": "MAT-CU01", "m2_iniciales": "2"})
    assert respuesta.status_code == 201, respuesta.text
    pieza = respuesta.json()
    assert pieza["estado"] == "RETAZO" and D(pieza["natural"]) == 0 and pieza["movimientos"] == []
    reutilizable = client.post(f"/cueros/{pieza['codigo']}/sobrante", json={"decision": "REUTILIZABLE"})
    assert reutilizable.status_code == 200 and reutilizable.json()["estado"] == "RETAZO"
    assert D(reutilizable.json()["disponible"]) == 2
    assert client.post("/cueros", json={"origen": "COMPRA", "material": "MAT-CU01", "m2_iniciales": "1"}).status_code == 422
    assert client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": "MAT-CU01",
                                        "m2_iniciales": "1", "fecha_de_compra": "2026-10-01"}).status_code == 422
    assert client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": "MAT-FL01",
                                        "m2_iniciales": "1"}).status_code == 422


def test_availability_orders_pieces_and_reports_missing_model_or_consumption(api):
    client, _ = api
    producto, _ = lote_para(client)
    compra = comprar(client, m2_iniciales="0.5")
    retazo = client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": "MAT-CU01",
                                          "m2_iniciales": "0.25"}).json()
    consulta = client.get("/cueros/alcanza", params={"producto": producto, "cantidad": "4"})
    assert consulta.status_code == 200
    datos = consulta.json()
    assert D(datos["necesario"]) == 1 and D(datos["disponible"]) == D("0.7")
    assert datos["alcanza"] is False and D(datos["faltante"]) == D("0.3")
    assert [p["codigo"] for p in datos["piezas"]] == [retazo["codigo"], compra["codigo"]]
    assert client.get("/cueros/alcanza", params={"producto": "PRD-9999", "cantidad": "1"}).status_code == 404
    assert client.get("/cueros/alcanza", params={"producto": producto, "cantidad": "0"}).status_code == 422


def test_summary_uses_current_price_and_dollar_when_purchase_price_is_absent(api):
    client, _ = api
    pieza = comprar(client, precio_pagado_por_m2=None, moneda=None)
    resumen = client.get("/cueros", params={"material": "MAT-CU01"})
    assert resumen.status_code == 200
    grupo = resumen.json()[0]
    assert grupo["avisos"] == []
    assert D(grupo["costo_desperdicio_ars"]) > 0
    assert grupo["piezas"][0]["codigo"] == pieza["codigo"]


def test_availability_suggests_same_leather_other_color_before_other_leather(api):
    client, role = api
    role["value"] = "admin"
    for color in ("Azul", "Negro"):
        creado = client.post("/colores", json={"nombre": color})
        assert creado.status_code == 201, creado.text
    role["value"] = "cotizador"
    producto, _ = lote_para(client, color="Azul")
    for material, color in (("MAT-CU01", "Azul"), ("MAT-CU01", "Negro"), ("MAT-CU02", "Negro")):
        creada = client.post("/cueros", json={"origen": "SOBRANTE_EXISTENTE", "material": material,
                                              "color": color, "m2_iniciales": "2" if color == "Negro" else "0.2"})
        assert creada.status_code == 201, creada.text
    consulta = client.get("/cueros/alcanza", params={"producto": producto, "cantidad": "4"})
    assert consulta.status_code == 200, consulta.text
    assert [(a["material"], a["color"]) for a in consulta.json()["alternativas"]] == [
        ("MAT-CU01", "Negro"), ("MAT-CU02", "Negro")]
    kit = client.post("/productos", json={"es_kit": True, "nombre_propio": "Kit sin modelo"})
    assert kit.status_code == 201, kit.text
    falta = client.get("/cueros/alcanza", params={"producto": kit.json()["codigo"], "cantidad": "1"})
    assert falta.status_code == 200 and "no tiene modelo o consumo" in falta.json()["mensaje"]
