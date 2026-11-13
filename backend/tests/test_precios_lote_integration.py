"""Margin column of the products grid (`POST /productos/precios-lote`) against disposable PostgreSQL.

Skipped without TEST_DATABASE_URL. Each test runs in a rolled-back transaction. Seeds used: MOD-0001 with MAT-CU01.
"""

from decimal import ROUND_HALF_UP, Decimal as D

import pytest
from sqlalchemy import func, select

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.main import app
from backend.models import PrecioVenta
from test_costos_fijos_correccion_integration import api  # noqa: F401  (fixture; its client also carries `.session`)


def como(role):
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-margen", email="a@x.com", role=role))


def un_producto(api):
    como("admin")
    respuesta = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"})
    assert respuesta.status_code == 201, respuesta.text
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    return respuesta.json()["codigo"]


def fila_de_la_lista(api, codigo):
    return next(f for f in api.get("/productos", params={"limit": 500}).json() if f["codigo"] == codigo)


def precios_guardados(api, codigo):
    return api.get(f"/productos/{codigo}/precio-venta").json()


def lote(api, *items):
    return api.post("/productos/precios-lote", json={"items": [{"codigo": c, "margen_pct": m} for c, m in items]})


def test_a_product_without_a_price_lists_empty_price_columns(api):
    codigo = un_producto(api)
    fila = fila_de_la_lista(api, codigo)
    assert (fila["precio_venta_ars"], fila["margen_pct"], fila["precio_final_ars"]) == (None, None, None)


def test_the_margin_creates_a_dated_price_of_cost_over_one_minus_margin(api):
    codigo = un_producto(api)
    costo = D(fila_de_la_lista(api, codigo)["costo_hoy_ars"])
    respuesta = lote(api, (codigo, "30"))
    assert respuesta.status_code == 200, respuesta.text
    fila = respuesta.json()[0]
    esperado = (costo / D("0.7")).quantize(D("0.01"), ROUND_HALF_UP)
    assert fila["codigo"] == codigo and D(fila["precio_venta_ars"]) == esperado and D(fila["margen_pct"]) == D("30")
    assert D(fila["precio_final_ars"]) >= D(fila["precio_venta_ars"])  # taxes only go on top of the net price
    assert fila == fila_de_la_lista(api, codigo)  # the response is the row the list shows afterwards
    historial = precios_guardados(api, codigo)
    assert len(historial) == 1 and D(historial[0]["precio_ars"]) == esperado and D(historial[0]["margen"]) == D("0.3")
    assert historial[0]["nota"] == "Margen desde la grilla de productos" and historial[0]["creado_por"] == "prueba-margen"


def test_saving_again_the_same_day_adds_a_row_and_the_newest_one_wins(api):
    codigo = un_producto(api)
    assert lote(api, (codigo, "30")).status_code == 200
    segunda = lote(api, (codigo, "45.5"))
    assert segunda.status_code == 200, segunda.text
    historial = precios_guardados(api, codigo)
    assert [D(p["margen"]) for p in historial] == [D("0.455"), D("0.3")]  # nothing was updated or deleted
    assert D(fila_de_la_lista(api, codigo)["margen_pct"]) == D("45.5")


def test_an_unknown_product_is_a_404_and_saves_nothing(api):
    codigo = un_producto(api)
    respuesta = lote(api, (codigo, "30"), ("PRD-9999", "30"))
    assert respuesta.status_code == 404 and "PRD-9999" in respuesta.json()["detail"]
    assert precios_guardados(api, codigo) == []


def test_a_product_without_a_computable_cost_is_a_422_naming_it_and_saves_nothing(api, monkeypatch):
    bueno = un_producto(api)
    malo = api.post("/productos", json={
        "modelo": "MOD-0002", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"}).json()["codigo"]
    real = servicios._costos_totales_de_hoy
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda session, codigos: {**real(session, codigos), malo: None})
    respuesta = lote(api, (bueno, "30"), (malo, "30"))
    assert respuesta.status_code == 422 and malo in respuesta.json()["detail"]
    assert precios_guardados(api, bueno) == [] and precios_guardados(api, malo) == []
    assert api.session.scalar(select(func.count()).select_from(PrecioVenta)) == 0


@pytest.mark.parametrize("margen", ["100", "-1", "abc"])
def test_a_margin_out_of_range_is_a_422_and_saves_nothing(api, margen):
    codigo = un_producto(api)
    assert lote(api, (codigo, margen)).status_code == 422
    assert precios_guardados(api, codigo) == []


def test_the_gerente_sees_the_prices_but_cannot_save_and_the_taller_sees_none(api):
    codigo = un_producto(api)
    assert lote(api, (codigo, "30")).status_code == 200
    como("gerente")
    assert fila_de_la_lista(api, codigo)["precio_venta_ars"] is not None
    assert lote(api, (codigo, "40")).status_code == 403
    como("taller")
    fila = fila_de_la_lista(api, codigo)
    assert (fila["precio_venta_ars"], fila["margen_pct"], fila["precio_final_ars"]) == (None, None, None)
    assert fila["costo_hoy_ars"] is not None  # the cost stays visible for the taller, as before
    como("admin")
    assert len(precios_guardados(api, codigo)) == 1
