"""Sale price from a margin over the sale price: price = cost / (1 - margin)."""

from decimal import Decimal as D

import pytest

from backend.costeo import precio_con_margen


def test_cost_150_and_margin_30_gives_214_29():
    assert precio_con_margen(D("150"), D("30")) == D("214.29")


def test_zero_margin_is_the_cost():
    assert precio_con_margen(D("150"), D("0")) == D("150.00")


def test_margin_is_over_the_price_not_over_the_cost():
    # 50 % over the price doubles the cost; a 50 % markup would only add half.
    assert precio_con_margen(D("100"), D("50")) == D("200.00")


@pytest.mark.parametrize("margen", [D("100"), D("120"), D("-1")])
def test_margin_outside_zero_to_99_is_rejected(margen):
    with pytest.raises(ValueError):
        precio_con_margen(D("100"), margen)


def test_suggested_price_uses_todays_cost(monkeypatch):
    from unittest.mock import MagicMock

    from backend import servicios

    monkeypatch.setattr(servicios, "_producto_o_404", lambda s, c: object())
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, c: {"PRD-1": D("150")})
    r = servicios.precio_sugerido_de_producto(MagicMock(), "PRD-1", D("30"))
    assert r["precio"] == D("214.29") and r["costo"] == D("150")


def test_suggested_price_without_cost_is_none(monkeypatch):
    from unittest.mock import MagicMock

    from backend import servicios

    monkeypatch.setattr(servicios, "_producto_o_404", lambda s, c: object())
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, c: {"PRD-1": None})
    assert servicios.precio_sugerido_de_producto(MagicMock(), "PRD-1", D("30"))["precio"] is None
