"""Per-unit consumption of a product, kits included (pure: no database)."""

from decimal import Decimal as D

from backend.consumo_lote import consumo_por_unidad
from backend.receta import Extra, ModeloReceta
from backend.servicios import DatosProducto


def producto(codigo, cuero_m2=None, componentes=(), extras=(), es_kit=False, cuero="MAT-CU01"):
    return DatosProducto(
        id=1, codigo=codigo, nombre=codigo, categoria=None, modelo_codigo=None, cuero=cuero, color=None,
        quien="INTERNA", estado_del_ciclo="ACTIVO", es_kit=es_kit, nota=None, fecha_de_alta=None,
        fecha_de_recotizacion=None, fecha_de_cierre=None,
        modelo=ModeloReceta(cuero_m2, None, None, None, None, None, None, None),
        extras=list(extras), componentes=list(componentes),
    )


def test_a_plain_product_gives_its_recipe_lines_per_unit():
    assert consumo_por_unidad(producto("A", D("0.25")), {}) == {("MAT-CU01", None): ("CUERO", D("0.25"))}


def test_extra_lines_are_added_to_the_model_lines():
    extra = Extra("MAT-CU01", "CUERO", None, D("0.1"))
    assert consumo_por_unidad(producto("A", D("0.25"), extras=[extra]), {})[("MAT-CU01", None)] == ("CUERO", D("0.35"))


def test_a_kit_counts_through_its_components_times_their_quantity():
    a, b = producto("A", D("0.25")), producto("B", D("0.5"))
    kit = producto("KIT", es_kit=True, componentes=[("A", D("2")), ("B", D("1"))])
    assert consumo_por_unidad(kit, {"A": a, "B": b})[("MAT-CU01", None)] == ("CUERO", D("1.0"))


def test_a_kit_loop_stops_instead_of_recursing_forever():
    uno = producto("K1", es_kit=True, componentes=[("K2", D("1"))])
    dos = producto("K2", D("0.5"), es_kit=True, componentes=[("K1", D("1"))])
    assert consumo_por_unidad(uno, {"K1": uno, "K2": dos}) == {("MAT-CU01", None): ("CUERO", D("0.5"))}
