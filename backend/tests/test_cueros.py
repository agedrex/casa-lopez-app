"""Pure leather calculations and monetary conversion without a database."""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

from backend import cueros


def pieza(inicial: str, compra: bool = True, precio: str | None = None, moneda: str | None = None):
    return SimpleNamespace(
        m2_iniciales=D(inicial), fecha_de_compra=date(2026, 10, 1) if compra else None,
        precio_pagado_por_m2=D(precio) if precio is not None else None, moneda=moneda,
    )


def movimiento(tipo: str, m2: str):
    return SimpleNamespace(tipo=tipo, m2=D(m2))


def test_purchase_cut_and_irrecoverable_remainder_follow_the_der_formula():
    piel = pieza("10")
    natural = movimiento("DESPERDICIO", "-1")
    compra = cueros.calcular_pieza(piel, [natural])
    assert compra == {"disponible": D("9"), "natural": D("1"), "irrecuperable": D("0"), "cortado": D("0")}

    corte = movimiento("CORTE", "-7.65")
    antes_de_cerrar = cueros.calcular_pieza(piel, [natural, corte])
    assert antes_de_cerrar["disponible"] == D("1.35")

    final = cueros.calcular_pieza(piel, [natural, corte, movimiento("DESPERDICIO", "-1.35")])
    assert final["disponible"] == 0
    assert final["irrecuperable"] == D("1.35")
    assert (final["natural"] + final["irrecuperable"]) / piel.m2_iniciales * D("100") == D("23.5")


def test_existing_remainder_has_no_natural_waste():
    assert cueros.calcular_pieza(pieza("2", compra=False), [])["natural"] == 0
    assert cueros.calcular_pieza(pieza("2", compra=False), [])["disponible"] == D("2")


def test_natural_waste_respects_the_existing_six_decimal_column():
    result = cueros.calcular_pieza(pieza("1.000005"), [movimiento("DESPERDICIO", "-0.100001")])
    assert result["natural"] == D("0.100001")
    assert result["irrecuperable"] == 0


def test_paid_price_uses_the_piece_currency_and_dollar():
    assert cueros._precio_ars(None, pieza("10", precio="20", moneda="ARS"), D("1500"), date(2026, 10, 1)) == D("20")
    assert cueros._precio_ars(None, pieza("10", precio="20", moneda="USD"), D("1500"), date(2026, 10, 1)) == D("30000")
    assert cueros._precio_ars(None, pieza("10", precio="20", moneda="USD"), None, date(2026, 10, 1)) is None
