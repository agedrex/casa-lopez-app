"""CVU profitability: sale price storage, per-product verdict and sales-mix scenario (S8-S11).

The pure assemblies and the service functions run against fakes; the HTTP gate against a stubbed service layer. The
PostgreSQL test at the bottom is skipped without TEST_DATABASE_URL.
"""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import PrecioVenta
from backend.servicios import FijosDelMes, armar_escenario, armar_rentabilidad

HOY = date(2026, 11, 4)


def fijos(total="600", cargados=True, pendientes=0, ficticios=False):
    return FijosDelMes(cargados=cargados, total_fabrica=D(total), pendientes=pendientes, ficticios=ficticios)


def escenario(items, *, costos=None, guardados=None, existentes=None, fijos_del_mes=None):
    """A: price 100, cost 60. B: saved price 200, cost 150. Fixed costs 600 (see test_costeo for the hand-made numbers)."""
    costos = {"A": D("60"), "B": D("150")} if costos is None else costos
    return armar_escenario(
        periodo="2026-11", items=items, existentes=set(costos) if existentes is None else existentes, costos=costos,
        guardados={"B": D("200")} if guardados is None else guardados, fijos=fijos_del_mes or fijos())


def item(codigo, unidades="10", precio=None):
    return {"codigo": codigo, "unidades": D(unidades), "precio": None if precio is None else D(precio)}


def sin_iibb_ni_gastos(monkeypatch):
    """The three new reads of the scenario service, as they are today: no IIBB alicuota, selling expense 0, no hours."""
    monkeypatch.setattr(servicios, "_alicuota_iibb", lambda s: D("0"))
    monkeypatch.setattr(servicios, "_gastos_venta_pct", lambda s: D("0"))
    monkeypatch.setattr(servicios, "_horas_de_confeccion", lambda s, ids: {})


def codigos(resultado):
    return [a["codigo"] for a in resultado["avisos"]]


def escenario_guia(*, iibb_alicuota=D("0.03"), gastos_venta_pct=D("0.05"), horas=None):
    """The guide's example: net price 100.000 (121.000 with IVA), cost 50.000, 5 % selling expense, 3 % IIBB."""
    return armar_escenario(
        periodo="2026-11", items=[item("A", "10", "100000")], existentes={"A"}, costos={"A": D("50000")}, guardados={},
        fijos=fijos(), iibb_alicuota=iibb_alicuota, gastos_venta_pct=gastos_venta_pct, horas=horas)


# --- CVU multiproducto (S1-S4) ----------------------------------------------------------------------------------------

def test_s1_iibb_is_the_net_price_times_the_alicuota_and_is_discounted_from_the_contribution():
    linea = escenario_guia(gastos_venta_pct=D("0"))["lineas"][0]
    assert linea["iibb_unidad"] == D("3000") and linea["margen_unidad"] == D("47000")
    assert "IIBB_SIN_ALICUOTA" not in codigos(escenario_guia())


def test_s1_without_an_iibb_alicuota_it_counts_zero_and_the_scenario_says_so():
    r = escenario_guia(iibb_alicuota=None, gastos_venta_pct=D("0"))
    assert r["lineas"][0]["iibb_unidad"] == D("0") and r["lineas"][0]["margen_unidad"] == D("50000")
    aviso = next(a for a in r["avisos"] if a["codigo"] == "IIBB_SIN_ALICUOTA")
    assert "Ingresos Brutos" in aviso["texto"] and "contador" in aviso["texto"]
    assert codigos(r)[-1] == "VOLUMEN_ESCENARIO" and r["confiable"] is True  # a missing rate is not a fixed-cost problem


def test_s2_the_selling_expense_is_the_net_price_times_the_parameter_and_the_guide_example_leaves_42000():
    r = escenario_guia()
    linea = r["lineas"][0]
    assert linea["gasto_venta_unidad"] == D("5000") and linea["iibb_unidad"] == D("3000")
    assert linea["margen_unidad"] == D("42000") and linea["contribucion_total"] == D("420000")
    assert r["resultado"]["margen_contribucion"] == D("420000") and r["resultado"]["margen_contribucion_pct"] == D("42")


def test_s2_the_break_even_uses_the_contribution_after_selling_expense_and_iibb():
    r = escenario_guia()  # fixed costs 600, 42.000 per unit -> 1 unit; the participation of the only line is 100 %
    assert r["resultado"]["equilibrio_unidades"] == D("1")
    assert r["lineas"][0]["participacion_pct"] == D("100")


def test_s3_the_margin_per_workshop_hour_is_listed_and_the_best_line_is_flagged():
    r = armar_escenario(
        periodo="2026-11", items=[item("A", precio="100"), item("B"), item("C", precio="100")], existentes={"A", "B", "C"},
        costos={"A": D("60"), "B": D("150"), "C": D("90")}, guardados={"B": D("200")}, fijos=fijos(),
        horas={"A": D("2"), "B": D("5"), "C": None})
    por_codigo = {linea["codigo"]: linea for linea in r["lineas"]}
    assert [linea["codigo"] for linea in r["lineas"]] == ["A", "B", "C"]  # the order of the request is kept
    assert por_codigo["A"]["horas_confeccion"] == D("2") and por_codigo["A"]["margen_por_hora"] == D("20")  # (100-60)/2
    assert por_codigo["B"]["margen_por_hora"] == D("10")  # (200-150)/5
    assert por_codigo["C"]["horas_confeccion"] is None and por_codigo["C"]["margen_por_hora"] is None
    assert [por_codigo[c]["ranking_por_hora"] for c in "ABC"] == [1, 2, None]
    assert r["mejor_por_hora"] == "A"


def test_s3_without_hours_nothing_is_invented():
    r = escenario([item("A", precio="100")])
    assert r["mejor_por_hora"] is None
    assert r["lineas"][0]["horas_confeccion"] is None and r["lineas"][0]["margen_por_hora"] is None
    assert r["lineas"][0]["ranking_por_hora"] is None
    zero = escenario_guia(horas={"A": D("0")})["lineas"][0]
    assert zero["margen_por_hora"] is None and zero["ranking_por_hora"] is None


def test_s4_with_no_iibb_and_no_selling_expense_every_old_number_is_identical():
    antes = escenario([item("A", "10", "100"), item("B", "5")])
    ahora = armar_escenario(
        periodo="2026-11", items=[item("A", "10", "100"), item("B", "5")], existentes={"A", "B"},
        costos={"A": D("60"), "B": D("150")}, guardados={"B": D("200")}, fijos=fijos(), iibb_alicuota=None,
        gastos_venta_pct=D("0"))
    assert antes["resultado"] == ahora["resultado"] and antes["fijos"] == ahora["fijos"]
    viejas = ("codigo", "unidades", "precio", "fuente_precio", "costo_variable", "margen_unidad", "margen_pct", "veredicto",
              "contribucion_total", "participacion_pct")
    assert [{k: l[k] for k in viejas} for l in antes["lineas"]] == [{k: l[k] for k in viejas} for l in ahora["lineas"]]
    assert all(l["iibb_unidad"] == D("0") and l["gasto_venta_unidad"] == D("0") for l in ahora["lineas"])
    assert codigos(ahora) == ["IIBB_SIN_ALICUOTA", "VOLUMEN_ESCENARIO"] and codigos(antes) == ["VOLUMEN_ESCENARIO"]


def test_s1_the_iibb_alicuota_is_read_from_the_active_ventas_tax_with_code_iibb():
    session = MagicMock()
    session.scalar.return_value = D("0.03")
    assert servicios._alicuota_iibb(session) == D("0.03")
    sql = str(session.scalar.call_args.args[0])
    assert "impuesto.codigo =" in sql and "impuesto.activo IS true" in sql and "impuesto.base =" in sql
    session.scalar.return_value = None  # no row, an inactive one or an empty alicuota: the same, no rate
    assert servicios._alicuota_iibb(session) is None


def test_s2_the_selling_expense_parameter_defaults_to_zero_when_missing_or_empty():
    session = MagicMock()
    session.scalar.return_value = D("0.05")
    assert servicios._gastos_venta_pct(session) == D("0.05")
    assert "GASTOS_VENTA_PCT" in str(session.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    for sin_valor in (None, D("0")):
        session.scalar.return_value = sin_valor
        assert servicios._gastos_venta_pct(session) == D("0")


def test_s1_s3_the_service_passes_the_alicuota_the_parameter_and_the_hours_to_the_scenario(monkeypatch):
    session = MagicMock()
    session.execute.return_value.all.return_value = [("A", 1)]
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"A": D("50000")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda s, ids: {})
    monkeypatch.setattr(servicios, "_fijos_de_fabrica", lambda s, periodos: {"2026-11": fijos("600")})
    monkeypatch.setattr(servicios, "_alicuota_iibb", lambda s: D("0.03"))
    monkeypatch.setattr(servicios, "_gastos_venta_pct", lambda s: D("0.05"))
    monkeypatch.setattr(servicios, "_horas_de_confeccion", lambda s, ids: {"A": D("3")})
    r = servicios.escenario_cvu(session, None, [item("A", precio="100000")], hoy=HOY)
    linea = r["lineas"][0]
    assert linea["margen_unidad"] == D("42000") and linea["margen_por_hora"] == D("14000") and r["mejor_por_hora"] == "A"
    assert "IIBB_SIN_ALICUOTA" not in codigos(r)


def test_s3_the_hours_come_from_the_model_of_each_product_and_a_kit_has_none():
    session = MagicMock()
    session.execute.return_value.all.return_value = [("A", D("2.5")), ("K", None)]
    assert servicios._horas_de_confeccion(session, {"A", "K"}) == {"A": D("2.5"), "K": None}
    assert servicios._horas_de_confeccion(session, set()) == {}


# --- Profitability of one product (S9) ------------------------------------------------------------------------------

def test_a_typed_price_beats_the_saved_one_and_is_marked_ingresado():
    r = armar_rentabilidad(codigo="A", costo=D("100"), precio_ingresado=D("125"), precio_guardado=D("999"))
    assert (r["fuente_precio"], r["precio"]) == ("INGRESADO", D("125"))
    assert r["margen_unidad"] == D("25") and r["margen_pct"] == D("20") and r["markup_pct"] == D("25")
    assert r["veredicto"] == "SALUDABLE" and r["motivo"] is None and r["costo_variable"] == D("100")


def test_without_a_typed_price_the_saved_one_is_used_and_marked_guardado():
    r = armar_rentabilidad(codigo="A", costo=D("100"), precio_ingresado=None, precio_guardado=D("90"))
    assert (r["fuente_precio"], r["precio"]) == ("GUARDADO", D("90"))
    assert r["margen_unidad"] == D("-10") and r["veredicto"] == "NO_CUBRE_VARIABLE"


def test_no_price_at_all_gives_a_reason_and_no_figures():
    r = armar_rentabilidad(codigo="A", costo=D("100"), precio_ingresado=None, precio_guardado=None)
    assert r["motivo"] == "SIN_PRECIO" and r["fuente_precio"] is None and r["precio"] is None
    assert r["margen_unidad"] is None and r["margen_pct"] is None and r["veredicto"] is None
    assert r["costo_variable"] == D("100")


def test_a_cost_that_cannot_be_computed_gives_a_reason_and_no_figures():
    r = armar_rentabilidad(codigo="A", costo=None, precio_ingresado=D("125"), precio_guardado=None)
    assert r["motivo"] == "SIN_COSTO_VARIABLE" and r["costo_variable"] is None
    assert r["margen_unidad"] is None and r["markup_pct"] is None and r["veredicto"] is None
    assert (r["fuente_precio"], r["precio"]) == ("INGRESADO", D("125"))


def test_without_price_and_without_cost_the_missing_price_is_reported_first():
    r = armar_rentabilidad(codigo="A", costo=None, precio_ingresado=None, precio_guardado=None)
    assert r["motivo"] == "SIN_PRECIO"


def test_the_row_22_cost_keeps_full_precision_in_the_verdict():
    r = armar_rentabilidad(codigo="A", costo=D("38760.6"), precio_ingresado=D("60000"), precio_guardado=None)
    assert r["margen_unidad"] == D("21239.4") and r["margen_pct"] == D("35.399")


# --- Scenario of the whole factory (S10) -----------------------------------------------------------------------------

def test_the_scenario_returns_the_weighted_break_even_and_the_share_of_each_product():
    r = escenario([item("A", precio="100"), item("B")])
    assert r["periodo"] == "2026-11" and r["confiable"] is True
    res = r["resultado"]
    assert res["motivo"] is None
    assert res["ingresos"] == D("3000") and res["margen_contribucion"] == D("900")
    assert res["margen_contribucion_pct"] == D("30") and res["costos_fijos"] == D("600")
    assert res["equilibrio_ingresos"] == D("2000") and res["equilibrio_unidades"] == D("14")
    assert res["utilidad"] == D("300")
    a, b = r["lineas"]
    assert (a["codigo"], a["fuente_precio"], a["contribucion_total"]) == ("A", "INGRESADO", D("400"))
    assert (b["codigo"], b["fuente_precio"], b["contribucion_total"], b["precio"]) == ("B", "GUARDADO", D("500"), D("200"))
    assert a["participacion_pct"] == D("400") / D("900") * 100
    assert b["participacion_pct"] == D("500") / D("900") * 100
    assert a["margen_unidad"] == D("40") and a["margen_pct"] == D("40") and a["veredicto"] == "SALUDABLE"
    assert r["omitidos"] == []


def test_the_fixed_costs_are_one_global_number_whatever_the_mix():
    primero = escenario([item("A", "10", "100"), item("B", "10")])
    segundo = escenario([item("A", "20", "100"), item("B", "10")])
    assert primero["resultado"]["costos_fijos"] == segundo["resultado"]["costos_fijos"] == D("600")
    assert primero["fijos"]["total_fabrica"] == D("600")
    assert primero["resultado"]["equilibrio_ingresos"] != segundo["resultado"]["equilibrio_ingresos"]


def test_products_without_price_or_cost_or_unknown_are_left_out_with_their_reason():
    r = escenario(
        [item("A", precio="100"), item("C"), item("D", precio="50"), item("E", precio="50")],
        costos={"A": D("60"), "C": D("10"), "D": None}, existentes={"A", "C", "D"}, guardados={})
    assert r["omitidos"] == [
        {"codigo": "C", "motivo": "SIN_PRECIO"},
        {"codigo": "D", "motivo": "SIN_COSTO_VARIABLE"},
        {"codigo": "E", "motivo": "PRODUCTO_NO_ENCONTRADO"},
    ]
    assert [linea["codigo"] for linea in r["lineas"]] == ["A"]
    assert r["resultado"]["ingresos"] == D("1000")  # only A is computed


def test_a_scenario_where_everything_is_left_out_has_no_numbers_and_says_why():
    r = escenario([item("C")], costos={"C": D("10")}, guardados={})
    assert r["resultado"]["motivo"] == "SIN_VENTAS" and r["resultado"]["equilibrio_unidades"] is None
    assert r["lineas"] == [] and r["omitidos"] == [{"codigo": "C", "motivo": "SIN_PRECIO"}]
    assert escenario([])["resultado"]["motivo"] == "SIN_VENTAS"


def test_a_mix_that_does_not_cover_the_variable_cost_has_no_break_even_and_no_shares():
    r = escenario([item("A", precio="50")])
    assert r["resultado"]["motivo"] == "MC_NO_POSITIVO"
    assert r["resultado"]["equilibrio_ingresos"] is None and r["resultado"]["utilidad"] is None
    assert r["lineas"][0]["contribucion_total"] == D("-100") and r["lineas"][0]["participacion_pct"] is None
    assert r["lineas"][0]["veredicto"] == "NO_CUBRE_VARIABLE"


def test_clean_fixed_costs_make_the_scenario_reliable_with_only_the_volume_notice():
    r = escenario([item("A", precio="100")])
    assert r["confiable"] is True
    assert r["avisos"] == [{"codigo": "VOLUMEN_ESCENARIO", "texto": "El volumen es el que cargaste, no ventas reales."}]


@pytest.mark.parametrize("fijos_del_mes, aviso", [
    (servicios.SIN_FIJOS, "SIN_FIJOS"),
    (fijos(pendientes=2), "FIJOS_PENDIENTES"),
    (fijos(ficticios=True), "FIJOS_FICTICIOS"),
])
def test_missing_pending_or_fictitious_fixed_costs_make_the_scenario_not_reliable(fijos_del_mes, aviso):
    r = escenario([item("A", precio="100")], fijos_del_mes=fijos_del_mes)
    assert r["confiable"] is False
    assert aviso in codigos(r) and codigos(r)[-1] == "VOLUMEN_ESCENARIO"


def test_all_the_fixed_cost_warnings_can_come_together():
    r = escenario([item("A", precio="100")], fijos_del_mes=fijos(pendientes=1, ficticios=True))
    assert codigos(r) == ["FIJOS_PENDIENTES", "FIJOS_FICTICIOS", "VOLUMEN_ESCENARIO"]
    assert r["confiable"] is False


# --- Service functions with a fake session (S8, S9, S10) --------------------------------------------------------------

def sesion_con_producto(producto=SimpleNamespace(id=7, codigo="PRD-0001")):
    session = MagicMock()
    session.scalar.return_value = producto
    return session


def test_a_sale_price_is_stored_with_its_date_user_and_note_and_committed():
    session = sesion_con_producto()
    r = servicios.guardar_precio_de_venta(
        session, "PRD-0001", precio_ars=D("60000.5000"), vigente_desde=date(2026, 11, 1), nota="Precio de góndola", quien="user-1")
    fila = session.add.call_args.args[0]
    assert isinstance(fila, PrecioVenta)
    assert (fila.producto_id, fila.precio_ars, fila.vigente_desde, fila.creado_por, fila.nota) == (
        7, D("60000.5000"), date(2026, 11, 1), "user-1", "Precio de góndola")
    session.commit.assert_called_once()
    assert r["producto"] == "PRD-0001" and r["precio_ars"] == D("60000.5000") and r["vigente_desde"] == date(2026, 11, 1)
    assert r["creado_por"] == "user-1" and r["nota"] == "Precio de góndola"


def test_the_date_defaults_to_today_and_the_user_and_note_are_optional():
    session = sesion_con_producto()
    r = servicios.guardar_precio_de_venta(session, "PRD-0001", precio_ars=D("10"), nota="", hoy=HOY)
    fila = session.add.call_args.args[0]
    assert fila.vigente_desde == HOY and fila.creado_por is None and fila.nota is None
    assert r["vigente_desde"] == HOY and r["creado_por"] is None


def test_the_sale_price_of_an_unknown_product_is_a_404_and_nothing_is_stored():
    session = sesion_con_producto(None)
    with pytest.raises(servicios.NoEncontrado, match="PRD-9999"):
        servicios.guardar_precio_de_venta(session, "PRD-9999", precio_ars=D("10"))
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("precio", [D("0"), D("-5"), None])
def test_a_price_that_is_not_positive_is_rejected_and_nothing_is_stored(precio):
    session = sesion_con_producto()
    with pytest.raises(servicios.DatosInvalidos, match="mayor que cero"):
        servicios.guardar_precio_de_venta(session, "PRD-0001", precio_ars=precio)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_the_history_is_read_newest_first_by_date_then_id_and_never_writes():
    session = sesion_con_producto()
    nuevo = PrecioVenta(producto_id=7, precio_ars=D("120"), vigente_desde=date(2026, 11, 1), creado_por="u", nota=None)
    viejo = PrecioVenta(producto_id=7, precio_ars=D("100"), vigente_desde=date(2026, 9, 1), creado_por=None, nota="antes")
    session.scalars.return_value.all.return_value = [nuevo, viejo]
    r = servicios.listar_precios_de_venta(session, "PRD-0001")
    assert [p["precio_ars"] for p in r] == [D("120"), D("100")]
    sql = str(session.scalars.call_args_list[0].args[0])  # the second read is the active taxes (see test_impuestos.py)
    assert "ORDER BY costos.precio_venta.vigente_desde DESC, costos.precio_venta.id DESC" in sql
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_the_history_of_an_unknown_product_is_a_404():
    with pytest.raises(servicios.NoEncontrado):
        servicios.listar_precios_de_venta(sesion_con_producto(None), "PRD-9999")


def test_the_latest_saved_price_is_the_first_row_of_each_product_in_date_then_id_order():
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        PrecioVenta(producto_id=1, precio_ars=D("30"), vigente_desde=date(2026, 11, 1)),
        PrecioVenta(producto_id=2, precio_ars=D("50"), vigente_desde=date(2026, 10, 1)),
        PrecioVenta(producto_id=1, precio_ars=D("20"), vigente_desde=date(2026, 9, 1)),
    ]
    assert servicios._ultimos_precios_de_venta(session, {1, 2}) == {1: D("30"), 2: D("50")}
    assert "ORDER BY costos.precio_venta.vigente_desde DESC, costos.precio_venta.id DESC" in str(session.scalars.call_args.args[0])
    assert servicios._ultimos_precios_de_venta(session, set()) == {}


def test_profitability_uses_todays_cost_and_the_saved_price_when_none_is_typed(monkeypatch):
    session = sesion_con_producto()
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": D("100")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda s, ids: {7: D("130")})
    r = servicios.rentabilidad_de_producto(session, "PRD-0001")
    assert (r["fuente_precio"], r["precio"], r["margen_unidad"]) == ("GUARDADO", D("130"), D("30"))
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_profitability_with_a_typed_price_does_not_even_look_for_the_saved_one(monkeypatch):
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": D("100")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda *a: pytest.fail("not needed"))
    r = servicios.rentabilidad_de_producto(sesion_con_producto(), "PRD-0001", D("125"))
    assert (r["fuente_precio"], r["margen_pct"]) == ("INGRESADO", D("20"))


def test_profitability_without_a_price_or_with_an_uncomputable_cost_says_why(monkeypatch):
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": D("100")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda s, ids: {})
    assert servicios.rentabilidad_de_producto(sesion_con_producto(), "PRD-0001")["motivo"] == "SIN_PRECIO"
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"PRD-0001": None})
    assert servicios.rentabilidad_de_producto(sesion_con_producto(), "PRD-0001", D("125"))["motivo"] == "SIN_COSTO_VARIABLE"


def test_profitability_of_an_unknown_product_is_a_404():
    with pytest.raises(servicios.NoEncontrado):
        servicios.rentabilidad_de_producto(sesion_con_producto(None), "PRD-9999")


def test_the_scenario_service_loads_fixed_costs_costs_and_saved_prices_and_saves_nothing(monkeypatch):
    session = MagicMock()
    session.execute.return_value.all.return_value = [("A", 1), ("B", 2)]
    pedidos = {}
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: pedidos.update(costos=codigos) or {"A": D("60"), "B": D("150")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda s, ids: pedidos.update(ids=ids) or {2: D("200")})
    monkeypatch.setattr(servicios, "_fijos_de_fabrica", lambda s, periodos: pedidos.update(periodos=periodos) or {"2026-11": fijos("600")})
    sin_iibb_ni_gastos(monkeypatch)
    r = servicios.escenario_cvu(session, None, [item("A", precio="100"), item("B"), item("Z")], hoy=HOY)
    assert pedidos == {"costos": {"A", "B"}, "ids": {1, 2}, "periodos": ["2026-11"]}
    assert r["periodo"] == "2026-11" and r["resultado"]["equilibrio_unidades"] == D("14") and r["confiable"] is True
    assert r["omitidos"] == [{"codigo": "Z", "motivo": "PRODUCTO_NO_ENCONTRADO"}]
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_the_scenario_service_uses_the_period_asked_and_a_period_without_rows_is_not_reliable(monkeypatch):
    session = MagicMock()
    session.execute.return_value.all.return_value = [("A", 1)]
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: {"A": D("60")})
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta", lambda s, ids: {})
    monkeypatch.setattr(servicios, "_fijos_de_fabrica", lambda s, periodos: {})
    sin_iibb_ni_gastos(monkeypatch)
    r = servicios.escenario_cvu(session, "2026-08", [item("A", precio="100")])
    assert r["periodo"] == "2026-08" and r["confiable"] is False and "SIN_FIJOS" in codigos(r)


def test_an_empty_scenario_never_touches_the_database(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(servicios, "_fijos_de_fabrica", lambda s, periodos: {})
    r = servicios.escenario_cvu(session, "2026-08", [])
    session.execute.assert_not_called()
    assert r["resultado"]["motivo"] == "SIN_VENTAS"


# --- HTTP layer (S8-S11) ----------------------------------------------------------------------------------------------

def con_rol(role):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="user-42", role=role))
    return TestClient(app)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield con_rol("admin")
    app.dependency_overrides.clear()


def test_posting_a_sale_price_passes_the_current_user_and_returns_money_as_strings(client, monkeypatch):
    visto = {}

    def falso(session, codigo, **kwargs):
        visto.update(codigo=codigo, **kwargs)
        return {"producto": codigo, "precio_ars": kwargs["precio_ars"], "vigente_desde": date(2026, 11, 4), "nota": kwargs["nota"],
                "creado_por": kwargs["quien"], "creado_en": None}
    monkeypatch.setattr(servicios, "guardar_precio_de_venta", falso)
    response = client.post("/productos/PRD-0001/precio-venta", json={"precio_ars": "60000.50", "nota": "x"})
    assert response.status_code == 201
    assert visto == {"codigo": "PRD-0001", "precio_ars": D("60000.50"), "vigente_desde": None, "nota": "x", "quien": "user-42"}
    assert response.json()["precio_ars"] == "60000.50" and response.json()["creado_por"] == "user-42"


@pytest.mark.parametrize("cuerpo", [
    {}, {"precio_ars": "0"}, {"precio_ars": "-5"}, {"precio_ars": "abc"}, {"precio_ars": "10", "vigente_desde": "ayer"},
    {"precio_ars": "10", "creado_por": "otro"}, {"precio_ars": "10", "moneda": "USD"},
])
def test_a_bad_sale_price_body_is_a_422_and_never_reaches_the_service(client, monkeypatch, cuerpo):
    monkeypatch.setattr(servicios, "guardar_precio_de_venta", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post("/productos/PRD-0001/precio-venta", json=cuerpo).status_code == 422


def test_an_unknown_product_is_a_404_on_every_new_product_route(client, monkeypatch):
    def no_existe(*a, **k):
        raise servicios.NoEncontrado("No existe el producto PRD-9999.")
    for nombre in ("guardar_precio_de_venta", "listar_precios_de_venta", "rentabilidad_de_producto"):
        monkeypatch.setattr(servicios, nombre, no_existe)
    respuestas = [
        client.post("/productos/PRD-9999/precio-venta", json={"precio_ars": "10"}),
        client.get("/productos/PRD-9999/precio-venta"),
        client.get("/productos/PRD-9999/rentabilidad"),
    ]
    assert [r.status_code for r in respuestas] == [404, 404, 404]
    assert respuestas[0].json() == {"detail": "No existe el producto PRD-9999."}


@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_a_user_without_a_writing_role_cannot_store_a_price(role, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        monkeypatch.setattr(servicios, "guardar_precio_de_venta", lambda *a, **k: pytest.fail("the service must not be called"))
        assert con_rol(role).post("/productos/PRD-0001/precio-venta", json={"precio_ars": "10"}).status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_the_history_and_the_profitability_are_open_to_the_gerente_role(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        monkeypatch.setattr(servicios, "listar_precios_de_venta", lambda session, codigo: [
            {"producto": codigo, "precio_ars": D("120"), "vigente_desde": date(2026, 11, 1), "nota": None, "creado_por": None, "creado_en": None}])
        visto = {}
        monkeypatch.setattr(servicios, "rentabilidad_de_producto", lambda session, codigo, precio: visto.update(precio=precio) or armar_rentabilidad(
            codigo=codigo, costo=D("100"), precio_ingresado=precio, precio_guardado=None))
        client = con_rol("gerente")
        assert client.get("/productos/PRD-0001/precio-venta").json()[0]["precio_ars"] == "120"
        cuerpo = client.get("/productos/PRD-0001/rentabilidad", params={"precio": "125.5"}).json()
        assert visto == {"precio": D("125.5")}
        assert cuerpo["fuente_precio"] == "INGRESADO" and cuerpo["margen_unidad"] == "25.5" and cuerpo["veredicto"] == "SALUDABLE"
        sin_precio = client.get("/productos/PRD-0001/rentabilidad").json()
        assert sin_precio["motivo"] == "SIN_PRECIO" and sin_precio["precio"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("params", [{"precio": "0"}, {"precio": "-5"}, {"precio": "abc"}])
def test_a_bad_typed_price_is_a_422_on_the_profitability_route(client, monkeypatch, params):
    monkeypatch.setattr(servicios, "rentabilidad_de_producto", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.get("/productos/PRD-0001/rentabilidad", params=params).status_code == 422


def test_the_scenario_response_carries_iibb_selling_expense_and_margin_per_hour_as_strings(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        monkeypatch.setattr(servicios, "escenario_cvu", lambda session, periodo, items: escenario_guia(
            iibb_alicuota=None, horas={"A": D("3")}))
        cuerpo = con_rol("admin").post("/cvu/escenario", json={"items": [{"codigo": "A", "unidades": "10"}]}).json()
        linea = cuerpo["lineas"][0]
        assert linea["iibb_unidad"] == "0" and linea["gasto_venta_unidad"] == "5000.0000"
        assert linea["horas_confeccion"] == "3" and linea["margen_por_hora"] == "15000.0000" and linea["ranking_por_hora"] == 1
        assert cuerpo["mejor_por_hora"] == "A"
        assert [a["codigo"] for a in cuerpo["avisos"]] == ["IIBB_SIN_ALICUOTA", "VOLUMEN_ESCENARIO"]
    finally:
        app.dependency_overrides.clear()


def test_the_scenario_is_admin_only_and_leaves_money_as_strings(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        visto = {}

        def falso(session, periodo, items):
            visto.update(periodo=periodo, items=items)
            return escenario([item("A", precio="100"), item("B")])
        monkeypatch.setattr(servicios, "escenario_cvu", falso)
        response = con_rol("admin").post("/cvu/escenario", json={
            "periodo": "2026-11", "items": [{"codigo": "A", "unidades": "10", "precio": "100"}, {"codigo": "B", "unidades": "10"}]})
        assert response.status_code == 200
        assert visto == {"periodo": "2026-11", "items": [
            {"codigo": "A", "unidades": D("10"), "precio": D("100")}, {"codigo": "B", "unidades": D("10"), "precio": None}]}
        cuerpo = response.json()
        assert cuerpo["resultado"]["equilibrio_unidades"] == "14" and cuerpo["resultado"]["margen_contribucion"] == "900"
        assert cuerpo["lineas"][0]["contribucion_total"] == "400" and cuerpo["confiable"] is True
        assert cuerpo["avisos"][-1]["codigo"] == "VOLUMEN_ESCENARIO"
    finally:
        app.dependency_overrides.clear()


def test_the_period_is_optional_in_the_scenario(client, monkeypatch):
    visto = {}
    monkeypatch.setattr(servicios, "escenario_cvu", lambda session, periodo, items: visto.update(periodo=periodo) or escenario([]))
    assert client.post("/cvu/escenario", json={"items": []}).status_code == 200
    assert visto == {"periodo": None}


@pytest.mark.parametrize("cuerpo", [
    {}, {"items": [{"codigo": "A", "unidades": "0"}]}, {"items": [{"codigo": "A", "unidades": "-1"}]},
    {"items": [{"codigo": "A", "unidades": "1", "precio": "0"}]}, {"items": [{"codigo": "A"}]},
    {"items": [{"codigo": "A", "unidades": "1", "costo": "5"}]}, {"periodo": "2026-13", "items": []},
    {"periodo": "noviembre", "items": []}, {"items": [], "fijos": "1"},
])
def test_a_bad_scenario_body_is_a_422_and_never_reaches_the_service(client, monkeypatch, cuerpo):
    monkeypatch.setattr(servicios, "escenario_cvu", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post("/cvu/escenario", json=cuerpo).status_code == 422


# --- The existing panel is untouched (differential check) ---------------------------------------------------------------

def test_the_cost_panel_still_has_the_same_shape_and_numbers():
    panel = servicios.armar_panel_de_costos(
        periodo="2026-11", precio=D("250"), hoy=HOY, lotes=[], items=[], costos={}, fijos={"2026-11": fijos("1000")},
        precios=[], dolar=None)
    assert set(panel) == {"periodo", "periodo_anterior", "actual", "anterior", "variacion_pct", "precios_que_subieron",
                          "precios_viejos", "dolar", "dolar_viejo", "avisos"}
    assert "cvu" in panel["actual"] and "equilibrio" in panel["actual"]


# --- PostgreSQL (skipped without TEST_DATABASE_URL) -----------------------------------------------------------------------

@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-cvu", role="admin"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def test_prices_are_stored_append_only_and_the_latest_one_drives_the_profitability(api):
    producto = api.post("/productos", json={
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"})
    assert producto.status_code == 201, producto.text
    codigo = producto.json()["codigo"]
    assert api.get(f"/productos/{codigo}/rentabilidad").json()["motivo"] == "SIN_PRECIO"
    # Seeds: MOD-0001 costs 22310.6 with a dollar of 1700 (see test_panel_tendencia_integration.py).
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    for precio, desde in (("50000", "2026-09-01"), ("70000", "2026-10-01"), ("65000", "2026-10-01")):
        assert api.post(f"/productos/{codigo}/precio-venta", json={"precio_ars": precio, "vigente_desde": desde}).status_code == 201
    assert api.post(f"/productos/{codigo}/precio-venta", json={"precio_ars": "0"}).status_code == 422
    historial = api.get(f"/productos/{codigo}/precio-venta").json()
    assert [p["precio_ars"] for p in historial] == ["65000.0000", "70000.0000", "50000.0000"]  # same date: the later id first
    assert all(p["creado_por"] == "prueba-cvu" for p in historial)
    guardado = api.get(f"/productos/{codigo}/rentabilidad").json()
    assert (guardado["fuente_precio"], guardado["precio"]) == ("GUARDADO", "65000.0000")
    assert D(guardado["margen_unidad"]) == D("65000") - D("22310.6") and guardado["veredicto"] == "SALUDABLE"
    ingresado = api.get(f"/productos/{codigo}/rentabilidad", params={"precio": "1"}).json()
    assert ingresado["fuente_precio"] == "INGRESADO" and ingresado["veredicto"] == "NO_CUBRE_VARIABLE"
    assert api.get("/productos/PRD-9999/rentabilidad").status_code == 404
    assert api.post("/productos/PRD-9999/precio-venta", json={"precio_ars": "10"}).status_code == 404
    escenario = api.post("/cvu/escenario", json={"periodo": "2027-05", "items": [{"codigo": codigo, "unidades": "10"}]}).json()
    assert escenario["lineas"][0]["fuente_precio"] == "GUARDADO"
    assert "SIN_FIJOS" in [a["codigo"] for a in escenario["avisos"]] and escenario["confiable"] is False


def test_s1_the_iibb_tax_is_also_found_by_its_name_because_the_grid_assigns_imp_codes():
    session = MagicMock()
    session.scalar.return_value = D("0.03")
    assert servicios._alicuota_iibb(session) == D("0.03")
    sql = str(session.scalar.call_args.args[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "ingresos brutos" in sql and "iibb%" in sql and "alicuota is not null" in sql


def test_s4_without_iibb_or_selling_expense_the_margin_keeps_the_exact_decimal_scale():
    costo = D("22310.60000000000000000")
    r = armar_escenario(periodo="2026-11", items=[item("A", "10", "30000")], existentes={"A"},
                        costos={"A": costo}, guardados={}, fijos=fijos(),
                        iibb_alicuota=None, gastos_venta_pct=D("0.0000"))
    linea = r["lineas"][0]
    assert linea["margen_unidad"].as_tuple() == (D("30000") - costo).as_tuple()
    assert linea["gasto_venta_unidad"] == 0 and linea["iibb_unidad"] == 0
