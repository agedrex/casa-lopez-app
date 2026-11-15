"""Transfers, sales, stock and real margin against disposable PostgreSQL (skipped without TEST_DATABASE_URL).

Each test runs inside an outer transaction that is rolled back, so the seeded database stays untouched.
Seeds used: MOD-0001 (cost computable with the seeded dollar and prices) and MARGEN_TRANSFERENCIA_PCT = 0.20.
SUPUESTO: validar con Robert.
"""

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.costeo import precio_con_margen
from backend.database import get_session
from backend.main import app
from backend.models import Transferencia, Venta


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-ventas", role="admin"))
    try:
        with TestClient(app) as client:
            client.session = session
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def producto(api):
    respuesta = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def lote(api, codigo, cantidad, estado):
    respuesta = api.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": "2026-11-01", "fecha_de_entrega": "2026-11-02", "estado": estado,
        "items": [{"producto": codigo, "cantidad": cantidad}]})
    assert respuesta.status_code == 201, respuesta.text


def mercaderia(api, unidades="10", costo="600"):
    respuesta = api.post("/reventa/lote", json={"nuevos": [{"nombre": "Lapicera de prueba", "costo": costo, "unidades": unidades}]})
    assert respuesta.status_code == 200, respuesta.text
    return next(p["codigo"] for p in respuesta.json() if p["nombre"] == "Lapicera de prueba")


def fila(api, codigo):
    return next((f for f in api.get("/stock").json()["filas"] if f["codigo"] == codigo), None)


def test_pg_a_transfer_freezes_cost_and_transfer_price_and_appears_in_the_month_list(api):
    codigo = producto(api)
    costo = servicios._costos_totales_de_hoy(api.session, {codigo})[codigo]
    assert costo is not None
    r = api.post("/transferencias", json={"producto": codigo, "unidades": "6", "nota": "caja 1"})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["codigo"] == "TRF-0001" and cuerpo["fecha"] == date.today().isoformat()
    assert D(cuerpo["costo_fabrica_unitario_ars"]) == costo.quantize(D("0.0001"))
    assert D(cuerpo["precio_transferencia_unitario_ars"]) == precio_con_margen(costo, D("20"))
    assert D(cuerpo["margen_transferencia_pct"]) == D("20")
    guardada = api.session.scalar(select(Transferencia).where(Transferencia.codigo == "TRF-0001"))
    assert guardada.creado_por == "prueba-ventas" and guardada.unidades == D("6")
    assert [t["codigo"] for t in api.get("/transferencias").json()] == ["TRF-0001"]
    assert api.get("/transferencias", params={"periodo": "2020-01"}).json() == []


def test_pg_stock_counts_only_finished_lots_and_flags_negatives_without_hiding_them(api):
    codigo = producto(api)
    lote(api, codigo, 10, "CERRADA")
    lote(api, codigo, 4, "LISTA")
    lote(api, codigo, 99, "EN_CONFECCION")  # not finished: it is not stock yet
    assert api.post("/transferencias", json={"producto": codigo, "unidades": "6"}).status_code == 201
    assert api.post("/ventas", json={"producto": codigo, "unidades": "4", "precio_unitario_ars": "50000"}).status_code == 201
    f = fila(api, codigo)
    assert (D(f["producido"]), D(f["transferido"]), D(f["vendido"])) == (D("14"), D("6"), D("4"))
    assert D(f["stock_fabrica"]) == D("8") and D(f["stock_tienda"]) == D("2") and f["inconsistente"] is False
    # Selling more than the store has is allowed, and shows up as a negative flagged row.
    assert api.post("/ventas", json={"producto": codigo, "unidades": "5", "precio_unitario_ars": "50000"}).status_code == 201
    f = fila(api, codigo)
    assert D(f["stock_tienda"]) == D("-3") and f["inconsistente"] is True and f["aviso"]
    assert api.get("/stock").json()["inconsistentes"] >= 1


def test_pg_resale_stock_is_bought_minus_sold_and_the_sale_freezes_the_purchase_cost(api):
    codigo = mercaderia(api)
    r = api.post("/ventas", json={"producto": codigo, "unidades": "3", "precio_unitario_ars": "1000"})
    assert r.status_code == 201, r.text
    assert D(r.json()["costo_compra_unitario_ars"]) == D("600") and r.json()["tipo"] == "MERCADERIA"
    f = fila(api, codigo)
    assert D(f["comprado"]) == D("10") and D(f["stock_tienda"]) == D("7") and f["stock_fabrica"] is None
    # A later cost change does not touch the frozen sale.
    api.post(f"/reventa/{codigo}/compras", json={"costo_unitario_ars": "900"})
    vieja = api.session.scalar(select(Venta).where(Venta.codigo == r.json()["codigo"]))
    assert vieja.costo_compra_unitario_ars == D("600")


def test_pg_real_margin_consolidated_is_factory_plus_store(api):
    codigo, mer = producto(api), mercaderia(api)
    transferencia = api.post("/transferencias", json={"producto": codigo, "unidades": "5"}).json()
    api.post("/ventas", json={"producto": codigo, "unidades": "2", "precio_unitario_ars": "50000"})
    api.post("/ventas", json={"producto": mer, "unidades": "3", "precio_unitario_ars": "1000"})
    r = api.get("/margen-real")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    fabrica, tienda, consolidado = (D(cuerpo[k]["margen"]) for k in ("fabrica", "tienda", "consolidado"))
    assert consolidado == fabrica + tienda
    unitario = D(transferencia["precio_transferencia_unitario_ars"]) - D(transferencia["costo_fabrica_unitario_ars"])
    assert fabrica == 2 * unitario
    assert D(cuerpo["ingresos"]) == D("103000")  # 2 x 50000 + 3 x 1000
    assert tienda == D("103000") - 2 * D(transferencia["precio_transferencia_unitario_ars"]) - 3 * D("600")
    assert {a["codigo"] for a in cuerpo["avisos"]} >= {"MARGEN_AL_VENDER"}


def test_pg_a_month_without_sales_says_so(api):
    cuerpo = api.get("/margen-real", params={"periodo": "2020-01"}).json()
    assert "VENTAS_SIN_CARGAR" in {a["codigo"] for a in cuerpo["avisos"]} and D(cuerpo["ingresos"]) == 0


def test_pg_the_database_refuses_a_sale_of_both_kinds_or_without_the_right_frozen_costs(api):
    codigo = producto(api)
    api.post("/transferencias", json={"producto": codigo, "unidades": "1"})
    base = {"codigo": "VEN-9001", "fecha": date.today(), "unidades": D("1"), "precio_unitario_ars": D("10")}
    id_producto = api.session.scalar(select(Transferencia.producto_id))
    for cambios in (
        {},  # no product at all
        {"producto_id": id_producto},  # a PRD sale without its frozen costs
        {"producto_id": id_producto, "costo_fabrica_unitario_ars": D("1"), "precio_transferencia_unitario_ars": D("2"),
         "costo_compra_unitario_ars": D("3")},  # a PRD sale with a purchase cost
    ):
        with pytest.raises(IntegrityError):
            with api.session.begin_nested():
                api.session.add(Venta(**base, **cambios))
                api.session.flush()
