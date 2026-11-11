"""Resale products: the cost/margin rules (pure) and the HTTP contract without a database."""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import reventa, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app


def compra(fecha, unidades, costo, venta=None, id=1):
    return SimpleNamespace(
        id=id, fecha=fecha, unidades=D(unidades), costo_unitario_ars=D(costo),
        precio_venta_unitario_ars=None if venta is None else D(venta), proveedor=None, nota=None, creado_por="u1",
        created_at=None,
    )


def producto(**cambios):
    base = {"codigo": "REV-0001", "nombre": "Lapicera", "proveedor": None, "nota": None, "activo": True}
    return SimpleNamespace(**{**base, **cambios})


def test_margin_is_profit_over_the_sale_price_and_missing_without_a_price():
    assert reventa._margen(D("600"), D("1000")) == (D("400"), D("0.4000"))
    assert reventa._margen(D("1200"), D("1000")) == (D("-200"), D("-0.2000"))  # selling below cost shows negative
    assert reventa._margen(D("600"), None) == (None, None)


def test_cost_is_the_unit_cost_of_the_latest_purchase_and_units_add_up():
    nuevas_primero = [compra(date(2026, 11, 1), "5", "700", "1500", id=2), compra(date(2026, 10, 1), "10", "600", "1000")]
    dato = reventa._a_dict(producto(), "Accesorios", nuevas_primero)
    assert dato["costo_unitario_ars"] == D("700") and dato["precio_venta_unitario_ars"] == D("1500")
    assert dato["unidades_compradas"] == D("15") and dato["compras"] == 2 and dato["ultima_compra"] == date(2026, 11, 1)
    assert dato["margen_unitario_ars"] == D("800")


def test_sale_price_falls_back_to_the_latest_purchase_that_has_one():
    nuevas_primero = [compra(date(2026, 11, 1), "5", "700", None, id=2), compra(date(2026, 10, 1), "10", "600", "1000")]
    dato = reventa._a_dict(producto(), None, nuevas_primero)
    assert dato["precio_venta_unitario_ars"] == D("1000") and dato["margen_unitario_ars"] == D("300")


def test_a_product_without_purchases_has_no_cost():
    dato = reventa._a_dict(producto(), None, [])
    assert dato["costo_unitario_ars"] is None and dato["margen_pct"] is None and dato["unidades_compradas"] == D(0)


def test_purchase_total_is_units_times_unit_cost():
    assert reventa._compra_a_dict(compra(date(2026, 11, 1), "12", "250.5"))["costo_total_ars"] == D("3006.0")


@pytest.mark.parametrize("cambios", [
    {"unidades": D(0)}, {"unidades": D(-1)}, {"costo_unitario_ars": D(0)}, {"precio_venta_unitario_ars": D(0)},
])
def test_invalid_purchases_are_rejected_before_touching_the_database(cambios):
    datos = {"unidades": D(1), "costo_unitario_ars": D(10), **cambios}
    with pytest.raises(servicios.DatosInvalidos):
        reventa.registrar_compra(MagicMock(), "REV-0001", **datos)


def test_a_product_needs_a_name():
    with pytest.raises(servicios.DatosInvalidos):
        reventa.crear(MagicMock(), nombre="  ", categoria=None, proveedor=None, nota=None)


# --- HTTP contract --------------------------------------------------------------------------------------------

FICHA = {
    "codigo": "REV-0001", "nombre": "Lapicera", "categoria": None, "proveedor": None, "nota": None, "activo": True,
    "costo_unitario_ars": D("600"), "precio_venta_unitario_ars": D("1000"), "margen_unitario_ars": D("400"),
    "margen_pct": D("0.4"), "ultima_compra": date(2026, 11, 1), "compras": 1, "unidades_compradas": D("10"),
    "historial": [],
}


def cliente(rol, monkeypatch):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=rol))
    monkeypatch.setattr(reventa, "listar", lambda session: [{k: v for k, v in FICHA.items() if k != "historial"}])
    monkeypatch.setattr(reventa, "registrar_compra", lambda session, codigo, **datos: FICHA)
    return TestClient(app)


@pytest.fixture(autouse=True)
def limpiar():
    yield
    app.dependency_overrides.clear()


def test_admin_lists_resale_products_with_money_as_strings(monkeypatch):
    respuesta = cliente("admin", monkeypatch).get("/reventa")
    assert respuesta.status_code == 200
    assert respuesta.json()[0]["costo_unitario_ars"] in ("600", "600.0", "600.0000")


@pytest.mark.parametrize("rol", ["gerente", "taller"])
def test_other_roles_cannot_read_or_write_resale(rol, monkeypatch):
    c = cliente(rol, monkeypatch)
    assert c.get("/reventa").status_code == 403
    assert c.post("/reventa/REV-0001/compras", json={"unidades": "1", "costo_unitario_ars": "1"}).status_code == 403


@pytest.mark.parametrize("cuerpo", [
    {"unidades": "0", "costo_unitario_ars": "10"}, {"unidades": "1", "costo_unitario_ars": "-5"},
    {"unidades": "1", "costo_unitario_ars": "10", "inventado": 1},
])
def test_invalid_purchase_bodies_answer_422(cuerpo, monkeypatch):
    assert cliente("admin", monkeypatch).post("/reventa/REV-0001/compras", json=cuerpo).status_code == 422
