"""Margin column of the products grid: `POST /productos/precios-lote` and the sale price fields of `GET /productos`.

Pure and mocked tests (no database). The same flow against PostgreSQL is in test_precios_lote_integration.py.
"""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import PrecioVenta

IVA = [{"codigo": "IVA", "nombre": "IVA", "alicuota": D("0.21")}]


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def con_rol(role):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="user-42", role=role))
    return TestClient(app), session


# --- Pure: the price columns of the grid ---------------------------------------------------------------------------

def test_a_product_without_a_saved_price_has_no_price_columns():
    vacio = {"precio_venta_ars": None, "margen_pct": None, "precio_final_ars": None}
    assert servicios.armar_precio_de_grilla(None, None, D("100"), IVA) == vacio
    assert servicios.armar_precio_de_grilla(None, D("0.3"), None, IVA) == vacio


def test_a_saved_margin_is_shown_as_a_percentage_and_the_final_price_adds_the_active_taxes():
    fila = servicios.armar_precio_de_grilla(D("1000"), D("0.300"), D("700"), IVA)
    assert fila["precio_venta_ars"] == D("1000") and fila["margen_pct"] == D("30")
    assert fila["precio_final_ars"] == D("1210")


def test_the_saved_margin_wins_over_the_one_the_cost_would_give():
    assert servicios.armar_precio_de_grilla(D("1000"), D("0.250"), D("100"), [])["margen_pct"] == D("25")


def test_a_price_typed_by_hand_gets_the_margin_it_leaves_over_todays_cost():
    fila = servicios.armar_precio_de_grilla(D("1000"), None, D("750"), [])
    assert fila["margen_pct"] == D("25.00") and fila["precio_final_ars"] == D("1000")
    assert servicios.armar_precio_de_grilla(D("1000"), None, D("1250"), [])["margen_pct"] == D("-25.00")  # sold at a loss


def test_a_price_typed_by_hand_without_a_computable_cost_has_no_margin_but_keeps_its_price():
    fila = servicios.armar_precio_de_grilla(D("1000"), None, None, IVA)
    assert fila["margen_pct"] is None and fila["precio_venta_ars"] == D("1000") and fila["precio_final_ars"] == D("1210")


# --- The list: who sees the prices --------------------------------------------------------------------------------

def _datos(n):
    return SimpleNamespace(id=n, codigo=f"PRD-000{n}", nombre="x", categoria=None, estado_del_ciclo="ACTIVO", es_kit=False,
                           nota=None, modelo_codigo="MOD-0001")


def _armar_lista(monkeypatch, precios):
    monkeypatch.setattr(servicios, "cargar_productos", lambda *a, **k: [_datos(1), _datos(2)])
    monkeypatch.setattr(servicios, "expandir_kits", lambda session, b: {})
    monkeypatch.setattr(servicios, "cargar_contexto", lambda session: None)
    monkeypatch.setattr(servicios, "_costo_hoy_seguro", lambda datos, ctx, catalogo: (None, []))
    monkeypatch.setattr(servicios, "_impuestos_activos", lambda session: IVA)
    monkeypatch.setattr(servicios, "_ultimos_precios_de_venta_completos", precios)


def test_the_list_carries_the_sale_price_columns_of_the_page_read_in_one_call(monkeypatch):
    llamadas = []

    def precios(session, ids):
        llamadas.append(ids)
        return {1: PrecioVenta(producto_id=1, precio_ars=D("1000"), margen=D("0.300"), vigente_desde=date(2026, 11, 1))}
    _armar_lista(monkeypatch, precios)
    filas = servicios.listar_productos(MagicMock())
    assert llamadas == [{1, 2}]
    assert (filas[0]["precio_venta_ars"], filas[0]["margen_pct"], filas[0]["precio_final_ars"]) == (D("1000"), D("30"), D("1210"))
    assert (filas[1]["precio_venta_ars"], filas[1]["margen_pct"], filas[1]["precio_final_ars"]) == (None, None, None)
    assert filas[0]["costo_hoy_ars"] is None and filas[0]["codigo"] == "PRD-0001"  # the old keys stay


def test_without_prices_the_list_reads_no_sale_price_and_leaves_the_columns_empty(monkeypatch):
    _armar_lista(monkeypatch, lambda *a: pytest.fail("the sale prices must not be read"))
    filas = servicios.listar_productos(MagicMock(), con_precios=False)
    assert [(f["precio_venta_ars"], f["margen_pct"], f["precio_final_ars"]) for f in filas] == [(None, None, None)] * 2


@pytest.mark.parametrize("role, esperado", [("admin", {}), ("gerente", {}), ("taller", {"con_precios": False})])
def test_only_the_taller_is_listed_without_sale_prices(monkeypatch, role, esperado):
    client, _ = con_rol(role)
    visto = {}
    monkeypatch.setattr(servicios, "listar_productos", lambda session, *a, **k: visto.update(k) or [])
    assert client.get("/productos").status_code == 200
    assert visto == esperado


# --- The save: service ---------------------------------------------------------------------------------------------

def _productos(*codigos):
    return [SimpleNamespace(id=i + 1, codigo=codigo) for i, codigo in enumerate(codigos)]


def _guardar(monkeypatch, items, costos, codigos_existentes=("PRD-0001", "PRD-0002")):
    session = MagicMock()
    session.scalars.return_value = _productos(*codigos_existentes)
    monkeypatch.setattr(servicios, "_costos_totales_de_hoy", lambda s, codigos: costos)
    monkeypatch.setattr(servicios, "listar_productos_por_codigo", lambda s, codigos: [{"codigo": c} for c in codigos])
    return session, lambda: servicios.guardar_precios_por_margen(session, items, quien="user-42", hoy=date(2026, 11, 13))


def test_each_item_appends_a_price_of_cost_over_one_minus_margin_with_the_margin_as_a_fraction(monkeypatch):
    session, guardar = _guardar(
        monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("30")}, {"codigo": "PRD-0002", "margen_pct": D("12.5")}],
        {"PRD-0001": D("700"), "PRD-0002": D("875")})
    assert guardar() == [{"codigo": "PRD-0001"}, {"codigo": "PRD-0002"}]
    filas = [llamada.args[0] for llamada in session.add.call_args_list]
    assert [(f.producto_id, f.precio_ars, f.margen) for f in filas] == [
        (1, D("1000.00"), D("0.30")), (2, D("1000.00"), D("0.125"))]
    for fila in filas:
        assert fila.vigente_desde == date(2026, 11, 13) and fila.creado_por == "user-42"
        assert fila.nota == "Margen desde la grilla de productos"
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_a_margin_of_zero_prices_at_cost(monkeypatch):
    session, guardar = _guardar(monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("0")}], {"PRD-0001": D("700")})
    guardar()
    fila = session.add.call_args.args[0]
    assert fila.precio_ars == D("700.00") and fila.margen == D("0")


def test_an_unknown_product_is_a_404_and_nothing_is_saved(monkeypatch):
    session, guardar = _guardar(
        monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("30")}, {"codigo": "PRD-9999", "margen_pct": D("30")}],
        {"PRD-0001": D("700")})
    with pytest.raises(servicios.NoEncontrado, match="PRD-9999"):
        guardar()
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


@pytest.mark.parametrize("costo", [None, D("0")])
def test_a_product_without_a_computable_cost_refuses_the_whole_save_naming_its_code(monkeypatch, costo):
    session, guardar = _guardar(
        monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("30")}, {"codigo": "PRD-0002", "margen_pct": D("30")}],
        {"PRD-0001": D("700"), "PRD-0002": costo})
    with pytest.raises(servicios.DatosInvalidos, match="PRD-0002"):
        guardar()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()  # the first row was added to the session, so it is rolled back with the rest


@pytest.mark.parametrize("margen", [D("100"), D("-1")])
def test_a_margin_out_of_range_is_refused_by_the_service_too(monkeypatch, margen):
    session, guardar = _guardar(monkeypatch, [{"codigo": "PRD-0001", "margen_pct": margen}], {"PRD-0001": D("700")})
    with pytest.raises(servicios.DatosInvalidos, match="PRD-0001"):
        guardar()
    session.commit.assert_not_called()


def test_a_database_error_while_saving_rolls_everything_back(monkeypatch):
    session, guardar = _guardar(monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("30")}], {"PRD-0001": D("700")})
    session.commit.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        guardar()
    session.rollback.assert_called_once()


def test_an_empty_or_repeated_or_oversized_save_is_refused_before_touching_the_database():
    session = MagicMock()
    with pytest.raises(servicios.DatosInvalidos):
        servicios.guardar_precios_por_margen(session, [])
    with pytest.raises(servicios.DatosInvalidos, match="repetido"):
        servicios.guardar_precios_por_margen(session, [{"codigo": "A", "margen_pct": D("1")}] * 2)
    with pytest.raises(servicios.DatosInvalidos, match="demasiados"):
        servicios.guardar_precios_por_margen(
            session, [{"codigo": f"P{i}", "margen_pct": D("1")} for i in range(servicios.MAX_FILAS_POR_LOTE + 1)])
    session.scalars.assert_not_called()


def test_a_second_save_the_same_day_adds_another_row_without_touching_the_first(monkeypatch):
    session, guardar = _guardar(monkeypatch, [{"codigo": "PRD-0001", "margen_pct": D("30")}], {"PRD-0001": D("700")})
    guardar()
    guardar()
    assert session.add.call_count == 2
    session.execute.assert_not_called()  # appended rows only: no UPDATE, no DELETE


# --- The save: API -------------------------------------------------------------------------------------------------

def test_the_route_passes_the_items_and_the_user_and_returns_money_as_strings(monkeypatch):
    client, _ = con_rol("admin")
    visto = {}
    fila = {"codigo": "PRD-0001", "nombre": "x", "categoria": None, "modelo": None, "estado_del_ciclo": "ACTIVO",
            "es_kit": False, "costo_hoy_ars": D("700"), "costo_hoy_usd": None, "avisos": [], "revisar": False,
            "motivos_revisar": [], "precio_venta_ars": D("1000.00"), "margen_pct": D("30"), "precio_final_ars": D("1210.00")}

    def falso(session, items, quien=None):
        visto.update(items=items, quien=quien)
        return [fila]
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", falso)
    respuesta = client.post("/productos/precios-lote", json={"items": [{"codigo": "PRD-0001", "margen_pct": "30"}]})
    assert respuesta.status_code == 200, respuesta.text
    assert visto == {"items": [{"codigo": "PRD-0001", "margen_pct": D("30")}], "quien": "user-42"}
    assert respuesta.json()[0]["precio_venta_ars"] == "1000.00" and respuesta.json()[0]["precio_final_ars"] == "1210.00"
    assert respuesta.json()[0]["margen_pct"] == "30"


@pytest.mark.parametrize("cuerpo", [
    {}, {"items": [{"codigo": "PRD-0001"}]}, {"items": [{"margen_pct": "30"}]},
    {"items": [{"codigo": "PRD-0001", "margen_pct": "100"}]}, {"items": [{"codigo": "PRD-0001", "margen_pct": "-1"}]},
    {"items": [{"codigo": "PRD-0001", "margen_pct": "abc"}]}, {"items": [{"codigo": "PRD-0001", "margen_pct": "30.55"}]},
    {"items": [{"codigo": "PRD-0001", "margen_pct": "30", "precio_ars": "1"}]},  # the price is never typed: it is computed
    {"items": [{"codigo": "PRD-0001", "margen_pct": "30"}], "fecha": "2026-11-13"},
])
def test_a_bad_body_is_a_422_and_never_reaches_the_service(monkeypatch, cuerpo):
    client, _ = con_rol("admin")
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post("/productos/precios-lote", json=cuerpo).status_code == 422


def test_the_errors_of_the_service_become_404_and_422(monkeypatch):
    client, _ = con_rol("admin")
    cuerpo = {"items": [{"codigo": "PRD-0001", "margen_pct": "30"}]}

    def no_existe(*a, **k):
        raise servicios.NoEncontrado("No existe el producto PRD-0001.")

    def sin_costo(*a, **k):
        raise servicios.DatosInvalidos("PRD-0001: no se puede calcular el costo de hoy, así que tampoco el precio.")
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", no_existe)
    assert client.post("/productos/precios-lote", json=cuerpo).status_code == 404
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", sin_costo)
    respuesta = client.post("/productos/precios-lote", json=cuerpo)
    assert respuesta.status_code == 422 and "PRD-0001" in respuesta.json()["detail"]


@pytest.mark.parametrize("role", ["gerente", "taller", None, "otro"])
def test_only_the_admin_saves_prices_from_the_grid(monkeypatch, role):
    client, session = con_rol(role)
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", lambda *a, **k: pytest.fail("the service must not be called"))
    respuesta = client.post("/productos/precios-lote", json={"items": [{"codigo": "PRD-0001", "margen_pct": "30"}]})
    assert respuesta.status_code == 403
    session.commit.assert_not_called()


def test_the_fixed_route_is_not_read_as_a_product_code(monkeypatch):
    client, _ = con_rol("admin")
    monkeypatch.setattr(servicios, "guardar_precios_por_margen", lambda *a, **k: [])
    assert client.post("/productos/precios-lote", json={"items": []}).status_code == 200
