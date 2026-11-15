"""Transfers to the store, real sales, derived stock and real margin (WO ventas-stock, T2 and T3).

No database needed: the pure builders (`armar_stock`, `armar_margen_real`), the services against a mocked session, the
HTTP contract and migration 0022. SUPUESTO: validar con Robert (every rule here is a proposal, none is confirmed).
The last block runs against disposable PostgreSQL (skipped without TEST_DATABASE_URL).
"""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint

from backend import reventa, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import Base, Transferencia, Venta
from backend.servicios import (
    SIN_FIJOS, DatosInvalidos, FijosDelMes, NoEncontrado, VentaCongelada, armar_margen_real, armar_stock,
)


@pytest.fixture(autouse=True)
def limpiar():
    yield
    app.dependency_overrides.clear()


# --- Stock (S3) ---------------------------------------------------------------------------------------------------

def test_factory_stock_is_finished_lots_minus_transfers_and_store_stock_is_transfers_minus_sales():
    r = armar_stock(
        producidos={"PRD-0001": D("10")}, transferidos={"PRD-0001": D("6")}, comprados={},
        vendidos={"PRD-0001": D("4")}, nombres={"PRD-0001": "Cartera Fucsia"})
    (fila,) = r["filas"]
    assert fila["tipo"] == "PRODUCTO" and fila["nombre"] == "Cartera Fucsia"
    assert (fila["producido"], fila["transferido"], fila["vendido"]) == (D("10"), D("6"), D("4"))
    assert fila["stock_fabrica"] == D("4") and fila["stock_tienda"] == D("2")
    assert fila["comprado"] is None and fila["inconsistente"] is False and fila["aviso"] is None
    assert r["inconsistentes"] == 0


def test_resale_stock_is_bought_minus_sold_and_has_no_factory_stock():
    r = armar_stock(
        producidos={}, transferidos={}, comprados={"MER-0001": D("5")}, vendidos={"MER-0001": D("2")},
        nombres={"MER-0001": "Lapicera"})
    (fila,) = r["filas"]
    assert fila["tipo"] == "MERCADERIA" and fila["stock_tienda"] == D("3") and fila["comprado"] == D("5")
    assert fila["producido"] is None and fila["transferido"] is None and fila["stock_fabrica"] is None


def test_a_negative_quantity_is_never_clamped_or_hidden_and_is_flagged_with_a_spanish_warning():
    r = armar_stock(
        producidos={"PRD-0001": D("2")}, transferidos={"PRD-0001": D("5")}, comprados={"MER-0001": D("1")},
        vendidos={"PRD-0001": D("9"), "MER-0001": D("3")}, nombres={"PRD-0001": "Cartera", "MER-0001": "Lapicera"})
    por_codigo = {f["codigo"]: f for f in r["filas"]}
    prd, mer = por_codigo["PRD-0001"], por_codigo["MER-0001"]
    assert prd["stock_fabrica"] == D("-3") and prd["stock_tienda"] == D("-4") and prd["inconsistente"] is True
    assert servicios.AVISO_STOCK_NEGATIVO_FABRICA in prd["aviso"] and servicios.AVISO_STOCK_NEGATIVO_TIENDA in prd["aviso"]
    assert mer["stock_tienda"] == D("-2") and mer["inconsistente"] is True
    assert mer["aviso"] == servicios.AVISO_STOCK_NEGATIVO_MERCADERIA
    assert r["inconsistentes"] == 2


def test_only_the_codes_with_some_movement_come_back_and_products_come_before_resale():
    r = armar_stock(
        producidos={"PRD-0002": D("1")}, transferidos={}, comprados={"MER-0001": D("1")}, vendidos={},
        nombres={"PRD-0002": "Zeta", "MER-0001": "Alfa"})
    assert [f["codigo"] for f in r["filas"]] == ["PRD-0002", "MER-0001"]
    assert armar_stock(producidos={}, transferidos={}, comprados={}, vendidos={}, nombres={}) == {"filas": [], "inconsistentes": 0}


def test_a_zero_stock_is_consistent():
    r = armar_stock(producidos={"PRD-0001": D("3")}, transferidos={"PRD-0001": D("3")}, comprados={},
                    vendidos={"PRD-0001": D("3")}, nombres={})
    assert r["filas"][0]["stock_fabrica"] == 0 and r["filas"][0]["stock_tienda"] == 0 and r["inconsistentes"] == 0
    assert r["filas"][0]["nombre"] == "PRD-0001"  # no name known: the code is shown


# --- Real margin (S5) ---------------------------------------------------------------------------------------------

def prd(unidades="2", precio="150", costo="80", transferencia="100", codigo="PRD-0001", nombre="Cartera"):
    return VentaCongelada(codigo, nombre, D(unidades), D(precio), costo_fabrica=D(costo), precio_transferencia=D(transferencia))


def mer(unidades="3", precio="1000", compra="600", codigo="MER-0001", nombre="Lapicera"):
    return VentaCongelada(codigo, nombre, D(unidades), D(precio), costo_compra=D(compra))


def fijos(total, **extra):
    return FijosDelMes(**{"cargados": True, "total_fabrica": D(total), "pendientes": 0, "ficticios": False, **extra})


def test_one_product_sale_splits_the_margin_between_factory_and_store():
    r = armar_margen_real(periodo="2026-11", ventas=[prd()], fijos_fabrica=fijos("10"), fijos_tienda=fijos("5"))
    assert r["ingresos"] == D("300") and r["unidades"] == D("2") and r["ventas"] == 1
    assert r["fabrica"]["margen"] == D("40")      # 2 x (100 - 80)
    assert r["tienda"]["margen"] == D("100")      # 300 - 2 x 100
    assert r["consolidado"]["margen"] == D("140")  # 300 - 2 x 80
    assert r["fabrica"]["utilidad"] == D("30") and r["tienda"]["utilidad"] == D("95") and r["consolidado"]["utilidad"] == D("125")
    assert r["consolidado"]["fijos"]["total"] == D("15")


def test_a_resale_sale_has_no_factory_margin_and_all_of_it_goes_to_the_store():
    r = armar_margen_real(periodo="2026-11", ventas=[mer()], fijos_fabrica=fijos("0"), fijos_tienda=fijos("0"))
    assert r["fabrica"]["margen"] == 0
    assert r["tienda"]["margen"] == D("1200") and r["consolidado"]["margen"] == D("1200")  # 3 x (1000 - 600)
    assert r["lineas"][0]["margen_fabrica"] is None and r["lineas"][0]["tipo"] == "MERCADERIA"


@pytest.mark.parametrize("ventas", [
    [prd()], [mer()], [prd(), mer()],
    [prd("7", "99.9999", "33.3333", "41.6667"), prd("0.5", "10", "12", "15", "PRD-0002"), mer("2.25", "10.5", "20.75")],
    [prd("1", "50", "80", "100")],  # selling below the transfer price: a negative store margin, still consistent
])
def test_the_transfer_margin_cancels_so_consolidated_is_exactly_factory_plus_store(ventas):
    r = armar_margen_real(periodo="2026-11", ventas=ventas, fijos_fabrica=fijos("7"), fijos_tienda=fijos("3"))
    assert r["consolidado"]["margen"] == r["fabrica"]["margen"] + r["tienda"]["margen"]
    assert r["consolidado"]["utilidad"] == r["fabrica"]["utilidad"] + r["tienda"]["utilidad"]
    assert sum(l["margen_consolidado"] for l in r["lineas"]) == r["consolidado"]["margen"]


def test_sales_of_the_same_product_are_added_in_one_line_and_lines_are_sorted_by_income():
    r = armar_margen_real(
        periodo="2026-11", ventas=[prd("1"), prd("3", "200", "80", "100"), mer()],
        fijos_fabrica=SIN_FIJOS, fijos_tienda=SIN_FIJOS)
    assert [l["codigo"] for l in r["lineas"]] == ["MER-0001", "PRD-0001"]  # 1800 of income before 750
    linea = next(l for l in r["lineas"] if l["codigo"] == "PRD-0001")
    assert linea["unidades"] == D("4") and linea["ingresos"] == D("750") and linea["margen_fabrica"] == D("80")
    assert r["lineas"][0]["ingresos"] >= r["lineas"][1]["ingresos"]


def test_costs_are_the_frozen_ones_so_a_sale_never_depends_on_todays_prices():
    # The builder receives only the snapshot: with the same frozen numbers the result cannot change.
    venta = prd()
    assert armar_margen_real(periodo="2026-11", ventas=[venta], fijos_fabrica=SIN_FIJOS, fijos_tienda=SIN_FIJOS) == \
        armar_margen_real(periodo="2026-11", ventas=[venta], fijos_fabrica=SIN_FIJOS, fijos_tienda=SIN_FIJOS)


def test_a_month_without_sales_warns_and_every_figure_is_zero():
    r = armar_margen_real(periodo="2026-11", ventas=[], fijos_fabrica=fijos("100"), fijos_tienda=fijos("50"))
    codigos = [a["codigo"] for a in r["avisos"]]
    assert "VENTAS_SIN_CARGAR" in codigos and r["confiable"] is False
    assert r["ingresos"] == 0 and r["lineas"] == [] and r["ventas"] == 0
    assert r["consolidado"]["utilidad"] == D("-150")  # only the fixed costs are left


def test_missing_pending_or_example_fixed_costs_make_the_month_not_reliable():
    r = armar_margen_real(periodo="2026-11", ventas=[prd()], fijos_fabrica=SIN_FIJOS, fijos_tienda=fijos("5", pendientes=2, ficticios=True))
    codigos = [a["codigo"] for a in r["avisos"]]
    assert {"SIN_FIJOS_FABRICA", "FIJOS_PENDIENTES", "FIJOS_FICTICIOS"} <= set(codigos) and "SIN_FIJOS_TIENDA" not in codigos
    assert r["confiable"] is False and r["consolidado"]["fijos"]["cargados"] is False
    assert r["consolidado"]["fijos"]["pendientes"] == 2 and r["consolidado"]["fijos"]["ficticios"] is True


def test_a_reliable_month_still_carries_the_informational_note_that_the_margin_is_recognized_when_sold():
    r = armar_margen_real(periodo="2026-11", ventas=[prd()], fijos_fabrica=fijos("10"), fijos_tienda=fijos("5"))
    assert r["confiable"] is True
    assert [a["codigo"] for a in r["avisos"]] == ["MARGEN_AL_VENDER"]
    assert "cuando la tienda vende" in r["avisos"][0]["texto"]


def test_month_ranges_roll_over_the_year():
    assert servicios._rango_del_mes("2026-11") == (date(2026, 11, 1), date(2026, 12, 1))
    assert servicios._rango_del_mes("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))


# --- Services against a mocked session (S1, S2, S4) ---------------------------------------------------------------

@pytest.fixture
def mundo(monkeypatch):
    """A session whose lookups are stubbed: product PRD-0001 costs 80 today and the transfer margin is 20 %."""
    session = MagicMock()
    session.scalar.return_value = None  # no previous TRF-/VEN- code
    producto = SimpleNamespace(id=5, codigo="PRD-0001")
    monkeypatch.setattr(servicios, "_producto_o_404", lambda s, codigo: producto)
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": D("80")})
    monkeypatch.setattr(servicios, "_margen_transferencia", lambda s: D("0.20"))
    monkeypatch.setattr(servicios, "_nombres_de_productos", lambda s, codigos: {c: f"Nombre de {c}" for c in codigos})
    monkeypatch.setattr(servicios, "stock", lambda *a, **k: pytest.fail("a write must never look at the stock"))
    return session


def fila_guardada(session):
    return session.add.call_args.args[0]


def test_a_transfer_freezes_todays_factory_cost_the_transfer_price_and_the_margin_used(mundo):
    r = servicios.registrar_transferencia(mundo, "PRD-0001", D("6"), fecha=date(2026, 11, 3), nota="  caja 1 ", quien="u1")
    fila = fila_guardada(mundo)
    assert isinstance(fila, Transferencia) and fila.codigo == "TRF-0001" and fila.producto_id == 5
    assert fila.unidades == D("6") and fila.fecha == date(2026, 11, 3) and fila.creado_por == "u1" and fila.nota == "caja 1"
    assert fila.costo_fabrica_unitario_ars == D("80.0000")
    assert fila.precio_transferencia_unitario_ars == D("100.00")  # 80 / (1 - 0.20)
    assert fila.margen_transferencia_pct == D("20.000")
    mundo.commit.assert_called_once()
    assert r["codigo"] == "TRF-0001" and r["producto"] == "PRD-0001" and r["producto_nombre"] == "Nombre de PRD-0001"
    assert r["total_transferido_ars"] == D("600.00")


def test_a_transfer_defaults_to_today_and_never_blocks_on_negative_stock(mundo):
    servicios.registrar_transferencia(mundo, "PRD-0001", D("1000"))  # `stock` is rigged to fail if it is read
    assert fila_guardada(mundo).fecha == date.today()


@pytest.mark.parametrize("unidades", [D("0"), D("-1"), None])
def test_a_transfer_with_no_positive_units_is_rejected_before_any_lookup(unidades):
    session = MagicMock()
    with pytest.raises(DatosInvalidos, match="mayores que cero"):
        servicios.registrar_transferencia(session, "PRD-0001", unidades)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_a_transfer_is_refused_when_the_cost_cannot_be_calculated(mundo, monkeypatch):
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": None})
    with pytest.raises(DatosInvalidos) as error:
        servicios.registrar_transferencia(mundo, "PRD-0001", D("1"))
    assert str(error.value) == "No se puede calcular el costo de ese producto todavía."
    mundo.add.assert_not_called()
    mundo.commit.assert_not_called()


def test_a_transfer_of_an_unknown_product_is_a_not_found(monkeypatch):
    def no_existe(session, codigo):
        raise NoEncontrado(f"No existe el producto {codigo}.")
    monkeypatch.setattr(servicios, "_producto_o_404", no_existe)
    with pytest.raises(NoEncontrado):
        servicios.registrar_transferencia(MagicMock(), "PRD-9999", D("1"))


def test_an_invalid_margin_parameter_is_a_clear_error_not_a_crash(mundo, monkeypatch):
    monkeypatch.setattr(servicios, "_margen_transferencia", lambda s: D("1.5"))  # 150 %
    with pytest.raises(DatosInvalidos, match="MARGEN_TRANSFERENCIA_PCT"):
        servicios.registrar_transferencia(mundo, "PRD-0001", D("1"))


def test_a_product_sale_freezes_the_factory_cost_and_the_transfer_price(mundo):
    r = servicios.registrar_venta(
        mundo, "PRD-0001", D("2"), D("150"), fecha=date(2026, 11, 4), canal=" Local ", nota=None, quien="u1")
    fila = fila_guardada(mundo)
    assert isinstance(fila, Venta) and fila.codigo == "VEN-0001" and fila.producto_id == 5
    assert fila.producto_reventa_id is None and fila.canal == "Local" and fila.creado_por == "u1"
    assert fila.precio_unitario_ars == D("150")
    assert fila.costo_fabrica_unitario_ars == D("80.0000") and fila.precio_transferencia_unitario_ars == D("100.00")
    assert fila.costo_compra_unitario_ars is None
    assert r["tipo"] == "PRODUCTO" and r["ingresos_ars"] == D("300") and r["producto_nombre"] == "Nombre de PRD-0001"


def test_a_resale_sale_freezes_the_cost_of_the_latest_purchase(mundo, monkeypatch):
    monkeypatch.setattr(reventa, "_por_codigo", lambda s, codigo: SimpleNamespace(id=9, codigo=codigo))
    monkeypatch.setattr(reventa, "_compras", lambda s, id_: [SimpleNamespace(costo_unitario_ars=D("650")), SimpleNamespace(costo_unitario_ars=D("600"))])
    r = servicios.registrar_venta(mundo, "MER-0001", D("3"), D("1000"), quien="u1")
    fila = fila_guardada(mundo)
    assert fila.producto_id is None and fila.producto_reventa_id == 9 and fila.codigo == "VEN-0001"
    assert fila.costo_compra_unitario_ars == D("650")
    assert fila.costo_fabrica_unitario_ars is None and fila.precio_transferencia_unitario_ars is None
    assert r["tipo"] == "MERCADERIA" and r["producto"] == "MER-0001"


def test_a_resale_sale_without_any_purchase_cost_is_rejected(mundo, monkeypatch):
    monkeypatch.setattr(reventa, "_por_codigo", lambda s, codigo: SimpleNamespace(id=9, codigo=codigo))
    monkeypatch.setattr(reventa, "_compras", lambda s, id_: [])
    with pytest.raises(DatosInvalidos, match="costo de compra"):
        servicios.registrar_venta(mundo, "MER-0001", D("1"), D("1000"))
    mundo.add.assert_not_called()


def test_a_sale_of_an_unknown_resale_product_is_a_not_found(mundo):
    mundo.scalar.return_value = None  # reventa._por_codigo finds nothing
    with pytest.raises(NoEncontrado):
        servicios.registrar_venta(mundo, "MER-9999", D("1"), D("1000"))


@pytest.mark.parametrize("unidades, precio, texto", [
    (D("0"), D("10"), "unidades"), (D("-2"), D("10"), "unidades"), (D("1"), D("0"), "precio"), (D("1"), D("-5"), "precio"),
    (D("1"), None, "precio"),
])
def test_a_sale_needs_positive_units_and_a_positive_price(unidades, precio, texto):
    session = MagicMock()
    with pytest.raises(DatosInvalidos, match=texto):
        servicios.registrar_venta(session, "PRD-0001", unidades, precio)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_a_sale_is_refused_when_the_product_cost_cannot_be_calculated(mundo, monkeypatch):
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": None})
    with pytest.raises(DatosInvalidos, match="No se puede calcular el costo de ese producto todavía."):
        servicios.registrar_venta(mundo, "PRD-0001", D("1"), D("150"))
    mundo.add.assert_not_called()


def test_a_sale_never_blocks_when_the_stock_would_go_negative(mundo):
    servicios.registrar_venta(mundo, "PRD-0001", D("99999"), D("150"))  # `stock` is rigged to fail if it is read
    mundo.commit.assert_called_once()


def test_the_next_code_continues_the_series(mundo):
    mundo.scalar.return_value = 41
    servicios.registrar_venta(mundo, "PRD-0001", D("1"), D("150"))
    assert fila_guardada(mundo).codigo == "VEN-0042"


# --- Model and migration ------------------------------------------------------------------------------------------

def checks(nombre):
    return {c.name: str(c.sqltext) for c in Base.metadata.tables[f"costos.{nombre}"].constraints if isinstance(c, CheckConstraint)}


def test_the_sale_table_demands_exactly_one_product_and_the_matching_frozen_costs():
    reglas = checks("venta")
    assert reglas["ck_venta_un_solo_producto"] == "(producto_id IS NULL) <> (producto_reventa_id IS NULL)"
    congelados = reglas["ck_venta_congelados_segun_producto"]
    assert "producto_id IS NOT NULL AND costo_fabrica_unitario_ars IS NOT NULL" in congelados
    assert "precio_transferencia_unitario_ars IS NOT NULL AND costo_compra_unitario_ars IS NULL" in congelados
    assert "producto_reventa_id IS NOT NULL AND costo_compra_unitario_ars IS NOT NULL" in congelados
    assert reglas["ck_venta_unidades_positivas"] == "unidades > 0" and reglas["ck_venta_precio_positivo"] == "precio_unitario_ars > 0"


def test_the_transfer_table_keeps_units_positive_and_the_margin_below_100():
    reglas = checks("transferencia")
    assert reglas["ck_transferencia_unidades_positivas"] == "unidades > 0"
    assert reglas["ck_transferencia_margen_en_rango"] == "margen_transferencia_pct >= 0 AND margen_transferencia_pct < 100"
    tabla = Base.metadata.tables["costos.transferencia"]
    assert not tabla.c.producto_id.nullable and not tabla.c.costo_fabrica_unitario_ars.nullable


def test_revision_0022_creates_both_tables_and_the_downgrade_drops_them_and_says_data_is_lost(monkeypatch):
    from test_migrations import load_revision
    operations, revision = load_revision(monkeypatch, "0022_ventas_transferencias.py")
    assert revision["revision"] == "0022_ventas_transferencias" and revision["down_revision"] == "0021_margen_transferencia"
    revision["upgrade"]()
    assert set(operations.metadata.tables) == {"costos.transferencia", "costos.venta"}
    venta = operations.metadata.tables["costos.venta"]
    assert {fk.target_fullname for fk in venta.foreign_keys} == {"costos.producto.id", "costos.producto_reventa.id"}
    revision["downgrade"]()
    assert operations.dropped == ["venta", "transferencia"]
    assert "lost" in revision["__doc__"]


# --- HTTP contract (S1, S2, S3, S5) -------------------------------------------------------------------------------

VENTA = {
    "codigo": "VEN-0001", "fecha": date(2026, 11, 4), "producto": "PRD-0001", "producto_nombre": "Cartera", "tipo": "PRODUCTO",
    "unidades": D("2"), "precio_unitario_ars": D("150"), "ingresos_ars": D("300"), "canal": None, "nota": None,
    "costo_fabrica_unitario_ars": D("80"), "precio_transferencia_unitario_ars": D("100"), "costo_compra_unitario_ars": None,
    "creado_por": "u1", "creado_en": None,
}
TRANSFERENCIA = {
    "codigo": "TRF-0001", "fecha": date(2026, 11, 3), "producto": "PRD-0001", "producto_nombre": "Cartera", "unidades": D("6"),
    "costo_fabrica_unitario_ars": D("80"), "precio_transferencia_unitario_ars": D("100"), "margen_transferencia_pct": D("20"),
    "total_transferido_ars": D("600"), "nota": None, "creado_por": "u1", "creado_en": None,
}


def cliente(rol, monkeypatch):
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u1", role=rol))
    llamadas = {}

    def guardar(nombre, resultado):
        def falso(session, *args, **kwargs):
            llamadas[nombre] = (args, kwargs)
            return resultado
        return falso
    monkeypatch.setattr(servicios, "registrar_venta", guardar("venta", VENTA))
    monkeypatch.setattr(servicios, "registrar_transferencia", guardar("transferencia", TRANSFERENCIA))
    monkeypatch.setattr(servicios, "listar_ventas", guardar("ventas", [VENTA]))
    monkeypatch.setattr(servicios, "listar_transferencias", guardar("transferencias", [TRANSFERENCIA]))
    monkeypatch.setattr(servicios, "stock", lambda session: {"filas": [], "inconsistentes": 0})
    monkeypatch.setattr(servicios, "margen_real", guardar("margen", armar_margen_real(
        periodo="2026-11", ventas=[prd()], fijos_fabrica=fijos("10"), fijos_tienda=fijos("5"))))
    return TestClient(app), llamadas


def test_admin_posts_a_sale_and_gets_201_with_money_as_strings_and_the_user_id_is_recorded(monkeypatch):
    c, llamadas = cliente("admin", monkeypatch)
    r = c.post("/ventas", json={"producto": "PRD-0001", "unidades": "2", "precio_unitario_ars": "150", "canal": "Local"})
    assert r.status_code == 201, r.text
    assert r.json()["codigo"] == "VEN-0001" and r.json()["ingresos_ars"] == "300"
    args, kwargs = llamadas["venta"]
    assert args == ("PRD-0001", D("2"), D("150")) and kwargs["quien"] == "u1" and kwargs["canal"] == "Local"


def test_admin_posts_a_transfer_and_gets_201(monkeypatch):
    c, llamadas = cliente("admin", monkeypatch)
    r = c.post("/transferencias", json={"producto": "PRD-0001", "unidades": "6", "fecha": "2026-11-03"})
    assert r.status_code == 201, r.text
    assert r.json()["precio_transferencia_unitario_ars"] == "100" and r.json()["margen_transferencia_pct"] == "20"
    args, kwargs = llamadas["transferencia"]
    assert args == ("PRD-0001", D("6")) and kwargs["fecha"] == date(2026, 11, 3) and kwargs["quien"] == "u1"


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/ventas", {"producto": "PRD-0001", "unidades": "0", "precio_unitario_ars": "150"}),
    ("/ventas", {"producto": "PRD-0001", "unidades": "1", "precio_unitario_ars": "-1"}),
    ("/ventas", {"producto": "PRD-0001", "unidades": "1"}),
    # The frozen costs are never accepted from the client.
    ("/ventas", {"producto": "PRD-0001", "unidades": "1", "precio_unitario_ars": "150", "costo_fabrica_unitario_ars": "1"}),
    ("/ventas", {"producto": "PRD-0001", "unidades": "1", "precio_unitario_ars": "150", "costo_compra_unitario_ars": "1"}),
    ("/transferencias", {"producto": "PRD-0001", "unidades": "0"}),
    ("/transferencias", {"producto": "PRD-0001", "unidades": "1", "precio_transferencia_unitario_ars": "1"}),
    ("/transferencias", {"producto": "PRD-0001", "unidades": "1", "margen_transferencia_pct": "50"}),
])
def test_invalid_or_calculated_fields_are_rejected_before_the_service(ruta, cuerpo, monkeypatch):
    c, llamadas = cliente("admin", monkeypatch)
    assert c.post(ruta, json=cuerpo).status_code == 422
    assert llamadas == {}


@pytest.mark.parametrize("rol", ["gerente", "taller", "otro", None])
def test_other_roles_get_403_on_every_new_route(rol, monkeypatch):
    c, llamadas = cliente(rol, monkeypatch)
    assert c.post("/ventas", json={"producto": "PRD-0001", "unidades": "1", "precio_unitario_ars": "1"}).status_code == 403
    assert c.post("/transferencias", json={"producto": "PRD-0001", "unidades": "1"}).status_code == 403
    for ruta in ("/ventas", "/transferencias", "/stock", "/margen-real"):
        assert c.get(ruta).status_code == 403, ruta
    assert llamadas == {}


def test_the_reads_answer_the_admin_and_pass_the_month(monkeypatch):
    c, llamadas = cliente("admin", monkeypatch)
    assert c.get("/ventas", params={"periodo": "2026-11"}).json()[0]["codigo"] == "VEN-0001"
    assert llamadas["ventas"][0] == ("2026-11",)
    assert c.get("/transferencias", params={"periodo": "2026-10"}).json()[0]["codigo"] == "TRF-0001"
    assert llamadas["transferencias"][0] == ("2026-10",)
    assert c.get("/stock").json() == {"filas": [], "inconsistentes": 0}
    margen = c.get("/margen-real", params={"periodo": "2026-11"})
    assert margen.status_code == 200, margen.text
    cuerpo = margen.json()
    assert cuerpo["fabrica"]["margen"] == "40" and cuerpo["tienda"]["margen"] == "100" and cuerpo["consolidado"]["margen"] == "140"
    assert cuerpo["confiable"] is True and cuerpo["avisos"][0]["codigo"] == "MARGEN_AL_VENDER"


@pytest.mark.parametrize("ruta", ["/ventas", "/transferencias", "/margen-real"])
@pytest.mark.parametrize("periodo", ["2026-13", "octubre", "2026-1"])
def test_an_invalid_month_is_rejected(ruta, periodo, monkeypatch):
    c, llamadas = cliente("admin", monkeypatch)
    assert c.get(ruta, params={"periodo": periodo}).status_code == 422
    assert llamadas == {}


def test_without_a_session_the_new_routes_answer_401():
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    with TestClient(app) as c:
        assert c.get("/stock").status_code == 401
        assert c.post("/ventas", json={}).status_code == 401
