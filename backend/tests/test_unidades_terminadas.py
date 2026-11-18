"""S5 of flujo-modelos-lotes-precio: a unit counts as produced only once its lot is finished (LISTA or CERRADA).

One criterion (`servicios.lotes_que_cuentan`) feeds the cost panel, the monthly trend and the /unidades screen, so they
cannot disagree. The pure tests run without a database; the integration ones are skipped without TEST_DATABASE_URL.
"""

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import LOT_STATES
from backend.servicios import (
    ESTADOS_TERMINADOS, FijosDelMes, ItemDatos, LoteDatos, _bloque_del_panel, armar_tendencia_de_costos,
    lotes_que_cuentan,
)

NOVIEMBRE = date(2026, 11, 10)


def lote(codigo, estado, *, entrega=None, envio=NOVIEMBRE, id=1):
    return LoteDatos(id=id, codigo=codigo, donde="INTERNA", taller=None, taller_nombre=None, persona=None,
                     persona_nombre=None, envio=envio, entrega=entrega, estado=estado, nota=None)


def item(lote_codigo, producto, cantidad, id=1):
    return ItemDatos(id=id, codigo=f"IT-{id}", lote=lote_codigo, producto=producto, cantidad=D(cantidad),
                     cotizado=None, pagado=None, nota=None)


FIJOS = FijosDelMes(cargados=True, total_fabrica=D("4000"), pendientes=0, ficticios=False)


def test_the_finished_states_are_lista_and_cerrada():
    assert ESTADOS_TERMINADOS == ("LISTA", "CERRADA")
    assert set(ESTADOS_TERMINADOS) <= set(LOT_STATES)
    assert servicios.ESTADOS_PRODUCIDOS == ESTADOS_TERMINADOS  # the factory stock uses the same criterion


@pytest.mark.parametrize("estado", LOT_STATES)
def test_the_panel_block_counts_units_and_variable_cost_only_from_finished_lots(estado):
    terminado = estado in ("LISTA", "CERRADA")
    bloque = _bloque_del_panel("2026-11", None, [lote("LOT-1", estado)], [item("LOT-1", "A", "10")],
                               {"A": D("100")}, FIJOS)
    assert bloque["unidades"] == (D("10") if terminado else D("0"))
    assert bloque["costo_variable_por_unidad"] == (D("100") if terminado else None)
    assert bloque["unidades_sin_costo"] == D("0")


def test_an_unfinished_lot_does_not_move_the_month_next_to_a_finished_one():
    lotes = [lote("LOT-1", "LISTA", id=1), lote("LOT-2", "PLANIFICADA", id=2), lote("LOT-3", "EN_CONFECCION", id=3)]
    items = [item("LOT-1", "A", "4", 1), item("LOT-2", "B", "50", 2), item("LOT-3", "A", "9", 3)]
    bloque = _bloque_del_panel("2026-11", None, lotes, items, {"A": D("100"), "B": D("999"), "C": None}, FIJOS)
    assert bloque["unidades"] == D("4") and bloque["costo_variable_por_unidad"] == D("100")
    assert bloque["fijo_por_unidad"] == D("1000")  # fixed costs over the 4 produced units, not over 63


def test_the_trend_uses_the_same_criterion_as_the_panel():
    lotes = [lote("LOT-1", "LISTA", id=1), lote("LOT-2", "EN_CORTE", id=2)]
    items = [item("LOT-1", "A", "6", 1), item("LOT-2", "A", "100", 2)]
    resultado = armar_tendencia_de_costos(
        hasta="2026-11", meses=1, lotes=lotes, items=items, costos={"A": D("100")}, fijos={"2026-11": FIJOS})
    assert resultado["meses"][0]["unidades"] == D("6")


def test_lotes_que_cuentan_is_finished_and_dated_in_the_period():
    lotes = [
        lote("LOT-1", "LISTA", id=1),
        lote("LOT-2", "CERRADA", envio=date(2026, 10, 30), entrega=date(2026, 11, 2), id=2),  # counts where it was delivered
        lote("LOT-3", "PLANIFICADA", id=3),
        lote("LOT-4", "LISTA", envio=None, id=4),  # finished but undated
        lote("LOT-5", "CERRADA", envio=date(2026, 10, 5), id=5),
    ]
    assert lotes_que_cuentan(lotes, "2026-11") == {"LOT-1", "LOT-2"}
    assert lotes_que_cuentan(lotes, "2026-10") == {"LOT-5"}
    # Without a period every finished lot counts, dated or not (the "Ver todo" of the screen).
    assert lotes_que_cuentan(lotes) == {"LOT-1", "LOT-2", "LOT-4", "LOT-5"}


# --- Against PostgreSQL -------------------------------------------------------------------------------------------

PERIODO = "2027-01"


@pytest.fixture
def api(local_postgres, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connection = local_postgres.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="prueba-unidades", role="admin"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer.rollback()
        connection.close()


def producto(api, modelo="MOD-0001"):
    respuesta = api.post("/productos", json={
        "modelo": modelo, "cuero": "MAT-CU01", "quien_lo_confecciona": "INTERNA", "fecha_de_alta": "2026-09-03"})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def crear_lote(api, codigo_producto, cantidad, *, estado="PLANIFICADA", envio="2027-01-10", entrega=None):
    respuesta = api.post("/ordenes", json={
        "donde_se_hace": "INTERNA", "fecha_de_envio": envio, "fecha_de_entrega": entrega, "estado": estado,
        "items": [{"producto": codigo_producto, "cantidad": cantidad}]})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["codigo"]


def avanzar(api, codigo, estado, **extra):
    respuesta = api.post(f"/ordenes/{codigo}/estado", json={"estado": estado, "fecha": "2027-01-20", **extra})
    assert respuesta.status_code in (200, 201), respuesta.text


def panel(api, periodo=PERIODO):
    respuesta = api.get("/panel/costos", params={"periodo": periodo})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["actual"]


def unidades(api, periodo=PERIODO):
    respuesta = api.get("/ordenes/unidades-por-producto", params={"periodo": periodo} if periodo else {})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


@pytest.fixture
def escenario(api):
    """A finished lot of 13 units next to a planned one of 8.5, the mismatch QA saw (21,5 on the panel against 13)."""
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    codigo = producto(api)
    terminado = crear_lote(api, codigo, "13", estado="LISTA")
    planificado = crear_lote(api, codigo, "8.5")
    return api, codigo, terminado, planificado


def test_the_panel_and_the_units_screen_show_the_same_total(escenario):
    api, codigo, _, _ = escenario
    pantalla = unidades(api)
    assert D(pantalla["total_unidades"]) == D("13")
    assert [(f["producto"], D(f["unidades"]), f["lotes"]) for f in pantalla["productos"]] == [(codigo, D("13"), 1)]
    assert D(panel(api)["unidades"]) == D(pantalla["total_unidades"])
    todo = unidades(api, None)
    assert D(todo["total_unidades"]) == D("13")


def test_creating_a_lot_does_not_move_the_variable_cost_until_it_is_finished(escenario):
    api, codigo, _, planificado = escenario
    antes = panel(api)
    # The planned lot is already there: it moves neither the units nor the variable cost.
    assert D(antes["unidades"]) == D("13") and antes["costo_variable_por_unidad"] is not None
    nuevo = crear_lote(api, codigo, "40")
    despues = panel(api)
    assert despues["unidades"] == antes["unidades"]
    assert despues["costo_variable_total"] == antes["costo_variable_total"]
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION"):
        avanzar(api, nuevo, estado)
        assert D(panel(api)["unidades"]) == D("13")
        assert D(unidades(api)["total_unidades"]) == D("13")
    avanzar(api, nuevo, "LISTA")
    assert D(panel(api)["unidades"]) == D("53")
    assert D(unidades(api)["total_unidades"]) == D("53")
    assert D(panel(api)["costo_variable_total"]) == D(antes["costo_variable_total"]) / 13 * 53


def test_the_screen_counts_a_lot_in_the_month_the_panel_does(api):
    """Delivered in February, sent in January: both say February (delivery date, else sending date)."""
    assert api.post("/dolar", json={"fecha": "2026-10-01", "ars_por_usd": "1700"}).status_code == 201
    codigo = producto(api)
    crear_lote(api, codigo, "5", estado="CERRADA", envio="2027-01-28", entrega="2027-02-02")
    crear_lote(api, codigo, "7", estado="LISTA", envio="2027-01-05")
    assert D(unidades(api, "2027-01")["total_unidades"]) == D("7") == D(panel(api, "2027-01")["unidades"])
    assert D(unidades(api, "2027-02")["total_unidades"]) == D("5") == D(panel(api, "2027-02")["unidades"])


def test_the_lot_detail_says_how_it_moves_the_variable_cost(escenario):
    api, _, terminado, planificado = escenario
    final = api.get(f"/ordenes/{terminado}").json()
    assert final["cuenta_en_costo_variable"] is True and final["cuenta_desde_estado"] == "LISTA"
    assert D(final["unidades"]) == D("13") and final["costo_total"] is not None and final["periodo"] == PERIODO
    pendiente = api.get(f"/ordenes/{planificado}").json()
    assert pendiente["cuenta_en_costo_variable"] is False and pendiente["cuenta_desde_estado"] == "LISTA"
    assert D(pendiente["unidades"]) == D("8.5")
    # The flag flips when the lot is finished.
    for estado in ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA"):
        avanzar(api, planificado, estado)
    assert api.get(f"/ordenes/{planificado}").json()["cuenta_en_costo_variable"] is True
