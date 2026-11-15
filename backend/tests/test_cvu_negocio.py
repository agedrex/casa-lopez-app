"""CVU of the factory and of the store: pure builder `armar_cvu_negocio` and the fixed-cost summary shape."""
from decimal import Decimal as D

from backend.servicios import FijosDelMes, armar_cvu_negocio, resumen_de_gastos_de_filas

FIJOS = FijosDelMes(cargados=True, total_fabrica=D("1000"), pendientes=0, ficticios=False)


def _fabrica(**extra):
    base = dict(
        ambito="FABRICA", periodo="2026-11", items=[{"codigo": "PRD-0001", "unidades": D("10"), "precio": None}],
        existentes={"PRD-0001"}, costos={"PRD-0001": D("80.00")}, guardados={"PRD-0001": D("100.00")}, fijos=FIJOS,
        margen_transferencia_pct=D("20"))
    return armar_cvu_negocio(**{**base, **extra})


def test_factory_sells_to_the_store_at_the_transfer_price_with_no_selling_taxes():
    r = _fabrica()
    linea = r["lineas"][0]
    assert r["ambito"] == "FABRICA" and r["margen_transferencia_pct"] == D("20")
    assert linea["fuente_precio"] == "TRANSFERENCIA" and linea["precio"] == D("100.00")
    assert linea["gasto_venta_unidad"] == 0 and linea["iibb_unidad"] == 0
    assert r["resultado"]["margen_contribucion"] == D("200.00")  # (100 - 80) x 10
    assert r["resultado"]["utilidad"] == D("-800.00")  # minus 1000 of fixed costs


def test_a_typed_price_wins_over_the_transfer_price():
    r = _fabrica(items=[{"codigo": "PRD-0001", "unidades": D("10"), "precio": D("90")}])
    assert r["lineas"][0]["fuente_precio"] == "INGRESADO" and r["lineas"][0]["precio"] == D("90")


def test_store_uses_its_own_fixed_costs_and_says_so_in_the_warnings():
    sin_fijos = FijosDelMes(cargados=False, total_fabrica=D("0"), pendientes=0, ficticios=False)
    r = _fabrica(ambito="TIENDA", fijos=sin_fijos, costos={"PRD-0001": D("100.00")}, guardados={"PRD-0001": D("150")})
    textos = " ".join(a["texto"] for a in r["avisos"])
    assert "de la tienda" in textos and "de la fábrica" not in textos
    assert r["lineas"][0]["fuente_precio"] == "GUARDADO" and r["confiable"] is False


def test_summary_groups_fixed_costs_by_ambito_and_category():
    filas = [
        ("FABRICA", "SUELDOS", D("500")), ("FABRICA", "ALQUILER", D("200")), ("TIENDA", "ALQUILER", D("300")),
        ("TIENDA", "SERVICIOS", None),
    ]
    r = resumen_de_gastos_de_filas(filas)
    por = {a["ambito"]: a for a in r["por_ambito"]}
    assert por["FABRICA"]["total"] == D("700") and por["TIENDA"]["total"] == D("300")
    assert por["TIENDA"]["pendientes"] == 1
    assert {c["categoria"]: c["total"] for c in por["FABRICA"]["categorias"]} == {"SUELDOS": D("500"), "ALQUILER": D("200")}
    assert r["total"] == D("1000")
