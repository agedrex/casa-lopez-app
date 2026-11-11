"""Soft delete of a fixed cost (costos-fijos-crud T1/T2, S3 and S5): pure and mocked tests, no database.

The PostgreSQL loop is in test_costos_fijos_anular_integration.py.
"""

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


def gasto(id, codigo, periodo="2026-10", anulado=False):
    return SimpleNamespace(
        id=id, codigo=codigo, periodo=periodo, concepto="Alquiler", fabrica_o_tienda="FABRICA", categoria="ALQUILER",
        persona_id=None, monto_ars_del_mes=D("1000"), ficticio=False, nota_fuente=None, reemplaza_a_id=None,
        anulado=anulado)


@pytest.fixture
def mes(monkeypatch):
    monkeypatch.setattr(servicios, "costos_fijos", lambda session, periodo=None: {"periodo": periodo})


def con_usuario(role="admin"):
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="usuario-de-prueba", role=role))
    return TestClient(app), session


# --- model and shared condition -------------------------------------------------------------------------------

def test_the_model_carries_a_not_null_anulado_flag_that_defaults_to_false():
    column = GastoPeriodo.__table__.c.anulado
    assert column.nullable is False and str(column.server_default.arg) == "false"
    assert str(column.type.compile(dialect=postgresql.dialect())) == "BOOLEAN"


def test_the_current_rows_condition_also_excludes_anulado_rows():
    sql = str(select(GastoPeriodo.id).where(servicios._gastos_vigentes()).compile(dialect=postgresql.dialect())).lower()
    assert "anulado" in sql and "reemplaza_a_id" in sql


# --- anular_gasto -----------------------------------------------------------------------------------------------

def test_annulling_sets_only_the_flag_and_returns_the_month(mes):
    viejo = gasto(7, "GF-0007")
    session = MagicMock()
    session.scalar.side_effect = [viejo, None]  # the row, then "nobody replaces it"
    resultado = servicios.anular_gasto(session, "GF-0007")
    assert viejo.anulado is True
    assert (viejo.monto_ars_del_mes, viejo.concepto, viejo.nota_fuente, viejo.reemplaza_a_id) == (D("1000"), "Alquiler", None, None)
    session.delete.assert_not_called()
    session.commit.assert_called_once()
    assert resultado == {"periodo": "2026-10"}


def test_annulling_an_unknown_row_is_not_found(mes):
    session = MagicMock()
    session.scalar.return_value = None
    with pytest.raises(servicios.NoEncontrado, match="GF-0099"):
        servicios.anular_gasto(session, "GF-0099")
    session.commit.assert_not_called()


def test_annulling_twice_is_a_conflict(mes):
    viejo = gasto(7, "GF-0007", anulado=True)
    session = MagicMock()
    session.scalar.side_effect = [viejo, None]
    with pytest.raises(servicios.Conflicto, match="anulado"):
        servicios.anular_gasto(session, "GF-0007")
    session.commit.assert_not_called()


def test_annulling_a_row_that_was_corrected_names_the_current_one(mes):
    viejo, actual = gasto(1, "GF-0001"), gasto(2, "GF-0002")
    session = MagicMock()
    session.scalar.side_effect = [viejo, actual, None]
    with pytest.raises(servicios.Conflicto, match="GF-0002"):
        servicios.anular_gasto(session, "GF-0001")
    assert viejo.anulado is False
    session.commit.assert_not_called()


def test_correcting_an_annulled_row_is_a_conflict(mes):
    session = MagicMock()
    session.scalar.side_effect = [gasto(7, "GF-0007", anulado=True), None]
    with pytest.raises(servicios.Conflicto, match="anulado"):
        servicios.corregir_gasto(session, "GF-0007", D("5"))
    session.commit.assert_not_called()


# --- guardar_gastos_en_lote: validation before touching the database -------------------------------------------

def test_a_code_in_changes_and_annulments_is_refused_before_touching_the_session():
    session = MagicMock()
    with pytest.raises(servicios.DatosInvalidos, match="GF-0001"):
        servicios.guardar_gastos_en_lote(
            session, "2026-10", [{"codigo": "GF-0001", "monto": D("5")}], [], anulados=["GF-0001"])
    assert session.mock_calls == []


def test_a_repeated_annulment_is_refused():
    session = MagicMock()
    with pytest.raises(servicios.DatosInvalidos, match="repetido"):
        servicios.guardar_gastos_en_lote(session, "2026-10", [], [], anulados=["GF-0001", "GF-0001"])
    assert session.mock_calls == []


def test_annulments_count_toward_the_row_limit():
    session = MagicMock()
    anulados = [f"GF-{n:04d}" for n in range(1, servicios.MAX_FILAS_POR_LOTE + 2)]
    with pytest.raises(servicios.DatosInvalidos, match=str(servicios.MAX_FILAS_POR_LOTE)):
        servicios.guardar_gastos_en_lote(session, "2026-10", [], [], anulados=anulados)
    assert session.mock_calls == []


def test_a_batch_of_only_annulments_is_not_empty(monkeypatch):
    viejo = gasto(7, "GF-0007")
    session = MagicMock()
    session.scalar.side_effect = [viejo, None]
    monkeypatch.setattr(servicios, "costos_fijos", lambda session, periodo=None: {"periodo": periodo})
    servicios.guardar_gastos_en_lote(session, "2026-10", [], [], anulados=["GF-0007"])
    assert viejo.anulado is True
    session.commit.assert_called_once()


def test_a_failing_batch_rolls_back_and_leaves_the_flag_to_the_transaction(monkeypatch):
    session = MagicMock()
    session.scalar.side_effect = [None]
    with pytest.raises(servicios.NoEncontrado, match="GF-0099"):
        servicios.guardar_gastos_en_lote(session, "2026-10", [], [], anulados=["GF-0099"])
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


# --- API ---------------------------------------------------------------------------------------------------------

def test_the_batch_body_accepts_person_note_and_annulments_and_defaults_them():
    cuerpo = api.GastosLoteIn(periodo="2026-10", cambios=[{"codigo": "GF-0001"}])
    assert cuerpo.anulados == []
    cambio = api.GastoCambioIn(codigo="GF-0001", persona=None, nota_fuente="Factura")
    assert cambio.model_dump(exclude_unset=True) == {"codigo": "GF-0001", "persona": None, "nota_fuente": "Factura"}


def test_the_batch_route_passes_annulments_and_new_fields_to_the_service(monkeypatch):
    client, _ = con_usuario()
    visto = {}

    def guardar(session, periodo, cambios, nuevos, **k):
        visto.update(periodo=periodo, cambios=cambios, nuevos=nuevos, **k)
        return {"periodo": periodo, "total_fabrica": D("0"), "total_tienda": D("0"), "total": D("0"),
                "pendientes": 0, "incluye_ficticios": False, "gastos": []}

    monkeypatch.setattr(servicios, "guardar_gastos_en_lote", guardar)
    respuesta = client.post("/costos-fijos/lote", json={
        "periodo": "2026-10", "cambios": [{"codigo": "GF-0001", "persona": None, "nota_fuente": "x"}],
        "anulados": ["GF-0002"]})
    assert respuesta.status_code == 200, respuesta.text
    assert visto["cambios"] == [{"codigo": "GF-0001", "persona": None, "nota_fuente": "x"}]
    assert visto["anulados"] == ["GF-0002"] and visto["nuevos"] == []


def test_the_annul_route_is_declared_and_passes_the_code_to_the_service(monkeypatch):
    rutas = [(r.path, tuple(sorted(r.methods))) for r in api.router.routes if hasattr(r, "methods")]
    assert ("/costos-fijos/{codigo}/anular", ("POST",)) in rutas
    client, _ = con_usuario()
    visto = []
    monkeypatch.setattr(servicios, "anular_gasto", lambda session, codigo: visto.append(codigo) or {
        "periodo": "2026-10", "total_fabrica": D("0"), "total_tienda": D("0"), "total": D("0"), "pendientes": 0,
        "incluye_ficticios": False, "gastos": []})
    respuesta = client.post("/costos-fijos/GF-0007/anular")
    assert respuesta.status_code == 200, respuesta.text
    assert visto == ["GF-0007"] and respuesta.json()["periodo"] == "2026-10"


@pytest.mark.parametrize("error, estado", [
    (servicios.NoEncontrado("No existe."), 404), (servicios.Conflicto("Ya anulado."), 409),
])
def test_the_annul_route_maps_domain_errors(monkeypatch, error, estado):
    client, _ = con_usuario()

    def fallar(*a, **k):
        raise error

    monkeypatch.setattr(servicios, "anular_gasto", fallar)
    assert client.post("/costos-fijos/GF-0007/anular").status_code == estado


@pytest.mark.parametrize("role", ["gerente", "taller", None])
def test_annulling_is_closed_to_read_only_roles(monkeypatch, role):
    client, _ = con_usuario(role)
    monkeypatch.setattr(servicios, "anular_gasto", lambda *a, **k: pytest.fail("must not be called"))
    assert client.post("/costos-fijos/GF-0007/anular").status_code == 403
