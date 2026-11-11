"""Correct a fixed cost / copy a month (panel-solido T1): pure and mocked tests, no database.

The PostgreSQL loop is in test_costos_fijos_correccion_integration.py.
"""

import inspect
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend import api, servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app
from backend.models import GastoPeriodo


@pytest.fixture(autouse=True)
def sin_base(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def gasto(id, codigo, periodo="2026-10", monto="1000", concepto="Alquiler", ficticio=False, persona_id=None,
          nota_fuente=None):
    return SimpleNamespace(
        id=id, codigo=codigo, periodo=periodo, concepto=concepto, fabrica_o_tienda="FABRICA", categoria="ALQUILER",
        persona_id=persona_id, monto_ars_del_mes=None if monto is None else D(monto), ficticio=ficticio,
        nota_fuente=nota_fuente, reemplaza_a_id=None, anulado=False)


@pytest.fixture
def escrito(monkeypatch):
    """Capture what the services would insert, and give out consecutive GF codes."""
    filas = []
    numeros = iter(range(900, 1000))
    monkeypatch.setattr(servicios, "_siguiente_numero", lambda *a, **k: next(numeros))
    monkeypatch.setattr(servicios, "_insertar", lambda session, fila, conflicto: filas.append(fila))
    monkeypatch.setattr(servicios, "costos_fijos", lambda session, periodo=None: {"periodo": periodo})
    return filas


# --- the shared "current rows only" condition (S6) -----------------------------------------------------------

def test_the_current_rows_condition_excludes_rows_that_another_row_replaces():
    sql = str(select(GastoPeriodo.id).where(servicios._gastos_vigentes()).compile(dialect=postgresql.dialect())).lower()
    assert "not (exists" in sql and "reemplaza_a_id" in sql


@pytest.mark.parametrize("funcion", [
    "costos_fijos", "_fijos_de_fabrica", "_hallazgos_de_gastos", "cargar_monto_de_gasto", "copiar_mes_de_gastos",
])
def test_every_reader_of_gasto_periodo_goes_through_the_shared_condition(funcion):
    assert "_gastos_vigentes()" in inspect.getsource(getattr(servicios, funcion))


def test_no_other_service_function_reads_gasto_periodo_without_the_shared_condition():
    fuente = inspect.getsource(servicios)
    lectores = {nombre for nombre, f in inspect.getmembers(servicios, inspect.isfunction)
                if f.__module__ == servicios.__name__ and "GastoPeriodo" in inspect.getsource(f)}
    # corregir_gasto and crear_gasto write; periodos_de_costos_fijos only lists months that still have a live row
    assert lectores <= {"costos_fijos", "_fijos_de_fabrica", "_hallazgos_de_gastos", "cargar_monto_de_gasto",
                        "copiar_mes_de_gastos", "corregir_gasto", "crear_gasto", "guardar_gastos_en_lote", "periodos_de_costos_fijos",
                        "_gastos_vigentes", "_gasto_actual_de", "_gastos_vigentes_del_mes", "anular_gasto",
                        "_gasto_para_cambiar"}, lectores
    assert fuente.count("def _gastos_vigentes") == 1


# --- corregir_gasto ------------------------------------------------------------------------------------------

def test_correcting_creates_a_new_row_that_points_to_the_old_one_and_leaves_the_old_one_alone(escrito):
    viejo = gasto(7, "GF-0007", persona_id=3, ficticio=True, nota_fuente="ejemplo")
    session = MagicMock()
    session.scalar.side_effect = [viejo, None]  # the row, then "nobody replaces it"
    resultado = servicios.corregir_gasto(session, "GF-0007", D("1500"))
    (nueva,) = escrito
    assert nueva.codigo == "GF-0900" and nueva.reemplaza_a_id == 7
    assert (nueva.periodo, nueva.concepto, nueva.fabrica_o_tienda, nueva.categoria, nueva.persona_id) == (
        "2026-10", "Alquiler", "FABRICA", "ALQUILER", 3)
    assert nueva.monto_ars_del_mes == D("1500") and nueva.ficticio is True  # copied unless the caller says otherwise
    assert viejo.monto_ars_del_mes == D("1000") and viejo.ficticio is True and viejo.nota_fuente == "ejemplo"
    session.delete.assert_not_called()
    session.commit.assert_called_once()
    assert resultado == {"periodo": "2026-10"}  # the whole month, like crear_gasto


def test_correcting_with_an_explicit_ficticio_and_note_uses_them(escrito):
    session = MagicMock()
    session.scalar.side_effect = [gasto(7, "GF-0007", ficticio=True), None]
    servicios.corregir_gasto(session, "GF-0007", D("0"), nota="Factura de octubre", ficticio=False)
    (nueva,) = escrito
    assert nueva.ficticio is False and nueva.nota_fuente == "Factura de octubre" and nueva.monto_ars_del_mes == D("0")


def test_the_new_row_notes_what_it_corrects_when_no_note_is_given(escrito):
    session = MagicMock()
    session.scalar.side_effect = [gasto(7, "GF-0007"), None]
    servicios.corregir_gasto(session, "GF-0007", D("5"))
    assert escrito[0].nota_fuente == "Corrige GF-0007"


def test_correcting_a_row_that_does_not_exist_is_not_found(escrito):
    session = MagicMock()
    session.scalar.return_value = None
    with pytest.raises(servicios.NoEncontrado, match="GF-0099"):
        servicios.corregir_gasto(session, "GF-0099", D("1"))
    assert escrito == []
    session.commit.assert_not_called()


def test_correcting_an_already_replaced_row_is_a_conflict_that_names_the_current_one(escrito):
    viejo, medio, actual = gasto(1, "GF-0001"), gasto(2, "GF-0002"), gasto(3, "GF-0003")
    session = MagicMock()
    session.scalar.side_effect = [viejo, medio, actual, None]  # GF-0001 -> GF-0002 -> GF-0003 (current)
    with pytest.raises(servicios.Conflicto, match="GF-0003"):
        servicios.corregir_gasto(session, "GF-0001", D("1"))
    assert escrito == []
    session.commit.assert_not_called()


def test_a_negative_amount_is_rejected_before_touching_the_session(escrito):
    session = MagicMock()
    with pytest.raises(servicios.DatosInvalidos, match="negativo"):
        servicios.corregir_gasto(session, "GF-0007", D("-0.01"))
    assert session.mock_calls == [] and escrito == []


# --- copiar_mes_de_gastos ------------------------------------------------------------------------------------

def sesion_de_copia(origen, filas_del_destino=0):
    session = MagicMock()
    session.scalar.return_value = filas_del_destino  # rows already in the target month
    session.scalars.return_value.all.return_value = origen
    return session


def test_copying_a_month_copies_the_current_rows_with_their_amounts(escrito):
    origen = [gasto(1, "GF-0001", monto="1000", ficticio=True, persona_id=4, concepto="Sueldo Ana"),
              gasto(2, "GF-0002", monto=None, concepto="Luz")]
    session = sesion_de_copia(origen)
    resultado = servicios.copiar_mes_de_gastos(session, "2026-10", "2026-11")
    assert [(f.codigo, f.periodo, f.concepto, f.monto_ars_del_mes, f.ficticio, f.persona_id) for f in escrito] == [
        ("GF-0900", "2026-11", "Sueldo Ana", D("1000"), True, 4), ("GF-0901", "2026-11", "Luz", None, False, None)]
    assert all("2026-10" in f.nota_fuente for f in escrito) and escrito[0].nota_fuente.endswith("(GF-0001)")
    assert all(f.reemplaza_a_id is None for f in escrito)  # a copy is not a correction
    session.commit.assert_called_once()
    assert resultado == {"periodo": "2026-11"}


def test_copying_without_amounts_leaves_them_pending_but_keeps_everything_else(escrito):
    session = sesion_de_copia([gasto(1, "GF-0001", monto="1000", ficticio=True, persona_id=4)])
    servicios.copiar_mes_de_gastos(session, "2026-10", "2026-11", con_montos=False)
    (nueva,) = escrito
    assert nueva.monto_ars_del_mes is None and nueva.ficticio is True and nueva.persona_id == 4
    assert (nueva.concepto, nueva.fabrica_o_tienda, nueva.categoria) == ("Alquiler", "FABRICA", "ALQUILER")


def test_copying_refuses_a_target_month_that_already_has_rows(escrito):
    session = sesion_de_copia([gasto(1, "GF-0001")], filas_del_destino=2)
    with pytest.raises(servicios.Conflicto, match="2026-11"):
        servicios.copiar_mes_de_gastos(session, "2026-10", "2026-11")
    assert escrito == []
    session.commit.assert_not_called()


def test_copying_refuses_an_empty_source_month(escrito):
    session = sesion_de_copia([])
    with pytest.raises(servicios.DatosInvalidos, match="2026-10"):
        servicios.copiar_mes_de_gastos(session, "2026-10", "2026-11")
    assert escrito == []
    session.commit.assert_not_called()


@pytest.mark.parametrize("desde, hasta", [("2026-13", "2026-11"), ("2026-10", "noviembre"), ("2026-10", "2026-10")])
def test_copying_validates_both_periods_before_touching_the_session(escrito, desde, hasta):
    session = MagicMock()
    with pytest.raises(servicios.DatosInvalidos):
        servicios.copiar_mes_de_gastos(session, desde, hasta)
    assert session.mock_calls == [] and escrito == []


# --- API: routes, gate and wiring ----------------------------------------------------------------------------

def con_usuario(role="admin"):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role=role))
    return TestClient(app), session


def test_both_routes_are_declared_and_the_static_one_is_not_shadowed():
    rutas = [(r.path, tuple(sorted(r.methods))) for r in api.router.routes if hasattr(r, "methods")]
    assert ("/costos-fijos/{codigo}/corregir", ("POST",)) in rutas and ("/costos-fijos/copiar", ("POST",)) in rutas
    # no POST route with a bare path parameter that could swallow /costos-fijos/copiar
    assert not [p for p, m in rutas if m == ("POST",) and p.startswith("/costos-fijos/{") and p.count("/") == 2]


def test_the_correct_route_passes_the_body_to_the_service(monkeypatch):
    client, _ = con_usuario()
    visto = {}
    monkeypatch.setattr(servicios, "corregir_gasto", lambda session, codigo, monto, **k: visto.update(
        codigo=codigo, monto=monto, **k) or {
            "periodo": "2026-10", "total_fabrica": D("1500"), "total_tienda": D("0"), "total": D("1500"),
            "pendientes": 0, "incluye_ficticios": False,
            "gastos": [{"codigo": "GF-0900", "concepto": "Alquiler", "fabrica_o_tienda": "FABRICA",
                        "categoria": "ALQUILER", "persona": None, "monto_ars_del_mes": D("1500"), "ficticio": False,
                        "nota_fuente": "Corrige GF-0007", "reemplaza_a": "GF-0007"}]})
    respuesta = client.post("/costos-fijos/GF-0007/corregir",
                            json={"monto_ars_del_mes": "1500", "nota": "Factura", "ficticio": False})
    assert respuesta.status_code == 201, respuesta.text
    assert visto == {"codigo": "GF-0007", "monto": D("1500"), "nota": "Factura", "ficticio": False}
    assert respuesta.json()["gastos"][0]["reemplaza_a"] == "GF-0007"


def test_the_correct_route_defaults_note_and_ficticio_to_none(monkeypatch):
    client, _ = con_usuario()
    visto = {}
    monkeypatch.setattr(servicios, "corregir_gasto", lambda session, codigo, monto, **k: visto.update(k) or {
        "periodo": "2026-10", "total_fabrica": D("0"), "total_tienda": D("0"), "total": D("0"), "pendientes": 0,
        "incluye_ficticios": False, "gastos": []})
    assert client.post("/costos-fijos/GF-0007/corregir", json={"monto_ars_del_mes": "0"}).status_code == 201
    assert visto == {"nota": None, "ficticio": None}


def test_the_copy_route_passes_the_body_to_the_service(monkeypatch):
    client, _ = con_usuario()
    visto = {}
    monkeypatch.setattr(servicios, "copiar_mes_de_gastos", lambda session, desde, hasta, **k: visto.update(
        desde=desde, hasta=hasta, **k) or {
            "periodo": hasta, "total_fabrica": D("0"), "total_tienda": D("0"), "total": D("0"), "pendientes": 0,
            "incluye_ficticios": False, "gastos": []})
    assert client.post("/costos-fijos/copiar", json={"desde": "2026-10", "hasta": "2026-11"}).status_code == 201
    assert visto == {"desde": "2026-10", "hasta": "2026-11", "con_montos": True}
    client.post("/costos-fijos/copiar", json={"desde": "2026-10", "hasta": "2026-11", "con_montos": False})
    assert visto["con_montos"] is False


def test_domain_errors_map_to_404_409_and_422(monkeypatch):
    client, _ = con_usuario()
    for error, estado in ((servicios.NoEncontrado("No existe."), 404), (servicios.Conflicto("Ya corregido."), 409),
                          (servicios.DatosInvalidos("Mes vacío."), 422)):
        def fallar(*a, _error=error, **k):
            raise _error
        monkeypatch.setattr(servicios, "corregir_gasto", fallar)
        monkeypatch.setattr(servicios, "copiar_mes_de_gastos", fallar)
        assert client.post("/costos-fijos/GF-0007/corregir", json={"monto_ars_del_mes": "1"}).status_code == estado
        assert client.post("/costos-fijos/copiar", json={"desde": "2026-10", "hasta": "2026-11"}).status_code == estado


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/costos-fijos/GF-0007/corregir", {"monto_ars_del_mes": "1"}),
    ("/costos-fijos/copiar", {"desde": "2026-10", "hasta": "2026-11"}),
])
@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_the_new_writes_are_closed_to_read_only_roles(monkeypatch, ruta, cuerpo, role):
    client, session = con_usuario(role)
    for nombre in ("corregir_gasto", "copiar_mes_de_gastos"):
        monkeypatch.setattr(servicios, nombre, lambda *a, **k: pytest.fail("the service must not be called"))
    assert client.post(ruta, json=cuerpo).status_code == 403
    session.commit.assert_not_called()


def test_reading_the_month_stays_open_to_the_admin_role(monkeypatch):
    client, _ = con_usuario("admin")
    monkeypatch.setattr(servicios, "costos_fijos", lambda session, periodo=None: {
        "periodo": "2026-10", "total_fabrica": D("0"), "total_tienda": D("0"), "total": D("0"), "pendientes": 0,
        "incluye_ficticios": False, "gastos": []})
    assert client.get("/costos-fijos", params={"periodo": "2026-10"}).status_code == 200
