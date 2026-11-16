"""Mercadería comprada del mes, imputada a la tienda (panel-costos T2, S8): `GET /costos-fijos/mercaderia`.

Against disposable PostgreSQL (skipped without TEST_DATABASE_URL). Month 2026-10 comes seeded with fixed costs
(some with an amount, some pending). The purchases of Mercadería are charged to the store only: the fixed-cost totals
of `/costos-fijos` do not change and nothing is written.
"""

from datetime import date
from decimal import Decimal as D

from sqlalchemy import func, select

from backend import reventa
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import CompraReventa, GastoPeriodo
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)

PERIODO = "2026-10"


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-negocio", email="a@x.com", role=role))


def producto(api, nombre, **compra):
    """A resale product with one first purchase (its costs and units are what the test passes)."""
    nuevo = {"nombre": nombre, **compra}
    return reventa.guardar_en_lote(api.session, [], [nuevo])[-1]["codigo"]


def comprar(api, codigo, fecha, unidades, costo):
    reventa.registrar_compra(api.session, codigo, unidades=unidades, costo_unitario_ars=costo, fecha=fecha)


def mercaderia(api, periodo=PERIODO):
    respuesta = api.get("/costos-fijos/mercaderia", params={"periodo": periodo})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_a_month_without_purchases_charges_nothing_to_the_store_beyond_its_fixed_costs(api):
    datos = mercaderia(api, "2031-01")
    assert datos["periodo"] == "2031-01"
    assert D(datos["total_mercaderia"]) == 0 and datos["compras"] == []
    assert D(datos["total_gastos_tienda"]) == 0 and D(datos["total_tienda"]) == 0


def test_the_purchases_of_the_month_are_charged_to_the_store_and_added_to_its_fixed_costs(api):
    gastos = api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    codigo = producto(api, "Billetera de reventa")
    comprar(api, codigo, date(2026, 10, 3), D("10"), D("600"))
    comprar(api, codigo, date(2026, 10, 20), D("4"), D("650.50"))
    datos = mercaderia(api)
    assert D(datos["total_mercaderia"]) == D("6000") + D("2602")
    assert D(datos["total_gastos_tienda"]) == D(gastos["total_tienda"])
    assert D(datos["total_tienda"]) == D(gastos["total_tienda"]) + D("8602")
    primera, segunda = datos["compras"]  # newest first
    assert segunda["producto"] == codigo and segunda["producto_nombre"] == "Billetera de reventa"
    assert D(primera["unidades"]) == 4 and D(primera["costo_unitario_ars"]) == D("650.50") and D(primera["total_ars"]) == D("2602")
    assert primera["fecha"] == "2026-10-20" and segunda["fecha"] == "2026-10-03"


def test_price_updates_without_units_and_purchases_of_other_months_do_not_count(api):
    codigo = producto(api, "Cinto de reventa")
    comprar(api, codigo, date(2026, 9, 30), D("5"), D("100"))
    comprar(api, codigo, date(2026, 11, 1), D("5"), D("100"))
    reventa.registrar_compra(api.session, codigo, costo_unitario_ars=D("999"), fecha=date(2026, 10, 15))  # price update
    datos = mercaderia(api)
    assert D(datos["total_mercaderia"]) == 0 and datos["compras"] == []


def test_the_fixed_cost_totals_and_the_database_are_left_alone(api):
    codigo = producto(api, "Llavero de reventa")
    comprar(api, codigo, date(2026, 10, 5), D("2"), D("300"))
    antes = api.get("/costos-fijos", params={"periodo": PERIODO}).json()
    filas = api.session.scalar(select(func.count()).select_from(GastoPeriodo))
    compras = api.session.scalar(select(func.count()).select_from(CompraReventa))
    mercaderia(api)
    assert api.get("/costos-fijos", params={"periodo": PERIODO}).json() == antes
    assert api.session.scalar(select(func.count()).select_from(GastoPeriodo)) == filas
    assert api.session.scalar(select(func.count()).select_from(CompraReventa)) == compras


def test_only_the_admin_reads_it_and_a_bad_period_is_rejected(api):
    como("admin")
    assert api.get("/costos-fijos/mercaderia", params={"periodo": "2026-13"}).status_code == 422
    for rol in ("consulta", "corte", "gerente", "taller"):
        como(rol)
        assert api.get("/costos-fijos/mercaderia", params={"periodo": PERIODO}).status_code == 403
