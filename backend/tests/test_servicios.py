"""Service layer, pure part: loaded rows in, dated quote out. No database needed."""

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from backend import servicios
from backend.costeo import ItemLote, PrecioVigente, Precios
from backend.receta import Extra, ModeloReceta
from backend.servicios import (
    Contexto, DatosInvalidos, DatosProducto, Parametros, cotizar_datos, columnas_cotizacion,
    fecha_de_cotizacion, marca_recotizar,
)

D0 = date(2026, 9, 1)
D1 = date(2026, 10, 1)
ETAPAS = {
    "MAT-CU01": "CUERO", "MAT-CU02": "CUERO", "MAT-FO02": "FORRO", "MAT-FL01": "FLEX",
    "MAT-GE01": "GOMA_EVA", "MAT-HE00": "HERRAJES", "MAT-HC01": "HILO_CEMENTO",
}
PRECIOS = Precios([
    PrecioVigente("MAT-CU01", None, D("24"), "USD", D0),
    PrecioVigente("MAT-CU02", None, D("80"), "USD", D0),
    PrecioVigente("MAT-FO02", None, D("4053"), "ARS", D0),
    PrecioVigente("MAT-FL01", None, D("10000"), "ARS", D0),
    PrecioVigente("MAT-GE01", None, D("5857"), "ARS", D0),
    PrecioVigente("MAT-HE00", None, D("1"), "USD", D0),
    PrecioVigente("MAT-HC01", None, D("2"), "USD", D0),
])
PARAMETROS = Parametros(
    desperdicio_default=D("0"), arreglos_pct=D("0"), tolerancia_desvio=D("0.05"),
    variacion_dolar=D("0.1"), iva_pct=D("0.21"), iva_es_costo=False,
)
CTX = Contexto(
    precios=PRECIOS, etapa_de_material=ETAPAS, desperdicio_manual={},
    dolares=[(D0, D("1545"))], parametros=PARAMETROS,
)
MODELO = ModeloReceta(
    cuero_m2=D("0.25"), forro_codigo="MAT-FO02", forro_m2=D("0.2"), flex_m2=D("0.45"),
    goma_eva_m2=D("0"), herrajes_usd=D("2"), hilo_cemento=D("1"), confeccion_estimada=D("12000"),
)
SIN_MODELO = ModeloReceta(None, None, None, None, None, None, None, None)


def producto(codigo="PRD-0001", **cambios):
    base = DatosProducto(
        id=1, codigo=codigo, nombre="Portafolio", categoria="Portafolios", modelo_codigo="MOD-0001",
        cuero="MAT-CU01", color=None, quien="INTERNA", estado_del_ciclo="EN_DEFINICION", es_kit=False,
        nota=None, fecha_de_alta=D0, fecha_de_recotizacion=None, fecha_de_cierre=None,
        modelo=MODELO, extras=[], lotes=[], componentes=[],
    )
    return replace(base, **cambios)


def total(datos, fecha=D0, ctx=CTX, catalogo=None):
    r = cotizar_datos(datos, ctx, fecha, catalogo or {datos.codigo: datos})
    return r.cotizado


def test_in_house_product_costs_materials_only_in_the_currency_of_each_price():
    # cuero 0.25 x 24 USD x 1545 + forro 0.2 x 4053 + flex 0.45 x 10000 + herrajes 2 USD + hilo 1 x 2 USD
    cotizado = total(producto())
    assert cotizado.completa and cotizado.desglose.total_ars == D("20760.6")
    assert cotizado.desglose.etapas["CONFECCION"] == 0


def test_a_new_dollar_moves_only_what_is_priced_in_dollars():
    ctx = replace(CTX, dolares=[(D1, D("1700")), (D0, D("1545"))])
    d = total(producto(), D1, ctx).desglose
    assert d.etapas["CUERO"] == D("10200") and d.etapas["FORRO"] == D("810.6") and d.etapas["FLEX"] == D("4500")
    assert d.total_ars == D("22310.6")


def test_external_product_uses_the_model_estimate_without_lots():
    d = total(producto(quien="EXTERNA")).desglose
    assert d.etapas["CONFECCION"] == D("12000") and d.total_ars == D("32760.6")


def test_external_product_uses_the_newest_lot_not_after_the_quote_date():
    lotes = [ItemLote(date(2026, 9, 10), D("11000"), D("10000")), ItemLote(date(2026, 12, 1), D("99999"), None)]
    datos = producto(quien="EXTERNA", lotes=lotes)
    assert total(datos, date(2026, 9, 20)).desglose.etapas["CONFECCION"] == D("10000")
    assert total(datos, date(2026, 9, 5)).desglose.etapas["CONFECCION"] == D("12000")


def test_extras_add_lines_to_the_quote():
    extra = Extra(material="MAT-CU02", etapa="CUERO", color=None, consumo=D("0.1"))
    d = total(producto(extras=[extra])).desglose
    assert d.etapas["CUERO"] == D("0.25") * 24 * 1545 + D("0.1") * 80 * 1545


def test_missing_price_makes_the_quote_incomplete_and_names_the_material():
    ctx = replace(CTX, precios=Precios([p for p in PRECIOS._filas if p.material != "MAT-FL01"]))
    cotizado = total(producto(), ctx=ctx)
    assert not cotizado.completa and "Sin precio para MAT-FL01 a esa fecha" in cotizado.avisos


def test_missing_dollar_means_no_breakdown():
    cotizado = total(producto(), ctx=replace(CTX, dolares=[]))
    assert cotizado.desglose is None and not cotizado.completa


def test_manual_waste_wins_over_the_default_and_the_default_applies_to_the_rest():
    ctx = replace(CTX, desperdicio_manual={"MAT-CU01": D("0.2")},
                  parametros=replace(PARAMETROS, desperdicio_default=D("0.1")))
    d = total(producto(), ctx=ctx).desglose
    assert d.etapas["CUERO"] == D("0.25") * D("1.2") * 24 * 1545
    assert d.etapas["FORRO"] == D("0.2") * D("1.1") * 4053


def test_vat_only_counts_when_it_is_a_product_cost_and_repairs_follow_the_percentage():
    base = total(producto()).desglose
    con_iva = total(producto(), ctx=replace(CTX, parametros=replace(PARAMETROS, iva_es_costo=True))).desglose
    assert con_iva.iva_compras == base.subtotal * D("0.21") and base.iva_compras == 0
    con_arreglos = total(producto(), ctx=replace(CTX, parametros=replace(PARAMETROS, arreglos_pct=D("0.05")))).desglose
    assert con_arreglos.arreglos == base.subtotal * D("0.05")


def kit_catalogo():
    kit = producto("PRD-0009", modelo_codigo=None, modelo=SIN_MODELO, cuero=None, es_kit=True,
                   componentes=[("PRD-0001", D("2"))], quien="INTERNA")
    return kit, {"PRD-0009": kit, "PRD-0001": producto()}


def test_kit_counts_components_at_subtotal_so_vat_and_repairs_apply_only_once():
    kit, catalogo = kit_catalogo()
    ctx = replace(CTX, parametros=replace(PARAMETROS, iva_es_costo=True, arreglos_pct=D("0.05")))
    d = total(kit, ctx=ctx, catalogo=catalogo).desglose
    componente = total(producto(), ctx=ctx).desglose
    assert d.componentes_kit == componente.subtotal * 2
    assert d.iva_compras == d.componentes_kit * D("0.21")
    assert d.arreglos == d.componentes_kit * D("0.05")


def test_kit_adds_quantity_times_each_components_own_total_at_the_same_date():
    kit, catalogo = kit_catalogo()
    d = total(kit, catalogo=catalogo).desglose
    assert d.componentes_kit == D("20760.6") * 2 and d.total_ars == D("41521.2")


def test_kit_with_an_incomplete_component_is_incomplete():
    kit, catalogo = kit_catalogo()
    catalogo["PRD-0001"] = producto(cuero=None, extras=[])
    ctx = replace(CTX, precios=Precios([p for p in PRECIOS._filas if p.material != "MAT-FL01"]))
    cotizado = total(kit, ctx=ctx, catalogo=catalogo)
    assert not cotizado.completa and any("PRD-0001" in a for a in cotizado.avisos)


def test_kit_without_components_is_incomplete():
    kit, catalogo = kit_catalogo()
    kit = replace(kit, componentes=[])
    assert not total(kit, catalogo={"PRD-0009": kit}).completa


def test_kit_cycles_are_rejected():
    a = producto("PRD-0001", es_kit=True, componentes=[("PRD-0002", D("1"))])
    b = producto("PRD-0002", es_kit=True, componentes=[("PRD-0001", D("1"))])
    with pytest.raises(DatosInvalidos, match="ciclo"):
        total(a, catalogo={"PRD-0001": a, "PRD-0002": b})


def test_kit_nesting_is_capped():
    chain = {f"PRD-{i:04d}": producto(f"PRD-{i:04d}", es_kit=True, componentes=[(f"PRD-{i + 1:04d}", D("1"))])
             for i in range(1, servicios.MAX_PROFUNDIDAD_KIT + 3)}
    with pytest.raises(DatosInvalidos, match="anidados"):
        total(chain["PRD-0001"], catalogo=chain)


@pytest.mark.parametrize("tipo, campo", [
    ("INICIAL", "fecha_de_alta"), ("RECOTIZACION", "fecha_de_recotizacion"), ("FINAL", "fecha_de_cierre"),
])
def test_each_quote_type_takes_its_date_from_the_product(tipo, campo):
    datos = producto(**{campo: date(2026, 11, 2)})
    assert fecha_de_cotizacion(datos, tipo, None) == date(2026, 11, 2)
    assert fecha_de_cotizacion(datos, tipo, date(2026, 12, 3)) == date(2026, 12, 3)


def test_a_missing_date_or_an_unknown_type_is_refused():
    with pytest.raises(DatosInvalidos, match="fecha"):
        fecha_de_cotizacion(producto(fecha_de_alta=None), "INICIAL", None)
    with pytest.raises(DatosInvalidos, match="tipo"):
        fecha_de_cotizacion(producto(), "OTRO", None)


def test_snapshot_columns_match_the_cotizacion_table_and_stay_decimal():
    d = total(producto()).desglose
    columnas = columnas_cotizacion(d)
    assert columnas["cuero"] == d.etapas["CUERO"] and columnas["total_ars"] == d.total_ars
    assert columnas["dolar"] == D("1545") and columnas["subtotal_etapas"] == d.subtotal
    assert all(isinstance(v, D) for v in columnas.values())
    from backend.models import Cotizacion
    assert set(columnas) <= {c.name for c in Cotizacion.__table__.columns}


def test_recotizar_flag_uses_cost_and_dollar_tolerances():
    d = total(producto(), D1, replace(CTX, dolares=[(D1, D("1700"))])).desglose
    assert marca_recotizar(d, D("20760.6"), D("1545"), PARAMETROS) is True
    assert marca_recotizar(d, d.total_ars, d.dolar, PARAMETROS) is False
    assert marca_recotizar(d, None, None, PARAMETROS) is None
    assert marca_recotizar(None, D("1"), D("1"), PARAMETROS) is None
    assert marca_recotizar(d, D("1"), D("1"), replace(PARAMETROS, tolerancia_desvio=None)) is None


def test_service_layer_never_touches_float():
    codigo = (Path(servicios.__file__)).read_text(encoding="utf-8")
    assert not re.search(r"\bfloat\s*\(", codigo)
