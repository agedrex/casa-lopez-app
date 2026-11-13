"""S8: the gerente runs the scenario simulator. `POST /cvu/escenario` is a POST only because of its body: it saves nothing."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend import servicios
from backend.auth import Usuario, get_verifier
from backend.database import get_session
from backend.main import app

SIN_PERMISO = {"detail": "No tenés permiso para esta acción."}
CUERPO = {"periodo": "2026-11", "items": []}


@pytest.fixture(autouse=True)
def limpiar(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    app.dependency_overrides.clear()


def cliente(role, session=None):
    session = session or MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_verifier] = lambda: (lambda request: Usuario(id="u", role=role))
    return TestClient(app, raise_server_exceptions=False), session


@pytest.mark.parametrize("role", ["gerente", "admin", "consulta", "cotizador"])
def test_gerente_and_admin_reach_the_scenario_service_and_nothing_is_written(monkeypatch, role):
    llamadas = []
    monkeypatch.setattr(servicios, "escenario_cvu", lambda session, periodo, items: llamadas.append((periodo, items)) or {})
    http, session = cliente(role)
    # 200 or 500 would both mean "past the gate"; the empty stub body only fails the response model, never the gate.
    assert http.post("/cvu/escenario", json=CUERPO).status_code not in (401, 403)
    assert llamadas == [("2026-11", [])]
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.delete.assert_not_called()


def test_the_real_scenario_service_answers_the_gerente_without_writing():
    http, session = cliente("gerente")
    session.execute.return_value.all.return_value = []
    session.execute.return_value.scalars.return_value.all.return_value = []
    session.execute.return_value.scalar_one_or_none.return_value = None
    respuesta = http.post("/cvu/escenario", json=CUERPO)
    assert respuesta.status_code == 200, respuesta.text
    session.add.assert_not_called()
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.delete.assert_not_called()


@pytest.mark.parametrize("role", ["taller", "corte", "otro", ""])
def test_taller_and_unknown_roles_cannot_run_the_scenario(monkeypatch, role):
    monkeypatch.setattr(servicios, "escenario_cvu", lambda *a, **k: pytest.fail("the service must not be called"))
    http, session = cliente(role)
    respuesta = http.post("/cvu/escenario", json=CUERPO)
    assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO
    session.commit.assert_not_called()


def test_the_scenario_without_a_session_is_401():
    app.dependency_overrides[get_verifier] = lambda: (lambda request: None)
    respuesta = TestClient(app).post("/cvu/escenario", json=CUERPO)
    assert respuesta.status_code == 401 and respuesta.json() == {"detail": "No autenticado."}


def test_the_gerente_still_cannot_write_through_any_other_post(monkeypatch):
    monkeypatch.setattr(servicios, "crear_producto", lambda *a, **k: pytest.fail("the service must not be called"))
    http, _ = cliente("gerente")
    for ruta in ("/productos", "/productos/PRD-0001/precio-venta", "/productos/precios-lote", "/modelos", "/precios", "/dolar"):
        respuesta = http.post(ruta, json={})
        assert respuesta.status_code == 403 and respuesta.json() == SIN_PERMISO, ruta
