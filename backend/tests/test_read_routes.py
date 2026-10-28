from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.database import get_session
from backend.main import app


@pytest.fixture
def read_client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    session = MagicMock()
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def test_database_state_reports_revision_and_domain_table_count(read_client):
    client, session = read_client
    session.execute.return_value.one.return_value = ("0004_semillas_v3", 25)
    response = client.get("/db/estado")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "alembic_revision": "0004_semillas_v3", "tablas_costos": 25}
    session.commit.assert_not_called()


def test_stages_are_ordered_and_expose_only_public_catalog_fields(read_client):
    client, session = read_client
    stages = [{"codigo": "CUERO", "orden": 1, "tipo": "MATERIAL", "va_siempre": True, "tratamiento": "VARIABLE"}]
    session.execute.return_value.mappings.return_value.all.return_value = stages
    response = client.get("/catalogo/etapas")
    assert response.status_code == 200
    assert response.json() == stages
    statement = str(session.execute.call_args.args[0])
    assert "ORDER BY" in statement and "costos.etapa" in statement
    selected = statement.split("FROM")[0]
    assert "nota" not in selected and "que_es_y_de_donde_viene" not in selected
    session.commit.assert_not_called()


@pytest.mark.parametrize("path", ["/db/estado", "/catalogo/etapas"])
def test_database_errors_never_reveal_driver_details(read_client, path):
    client, session = read_client
    session.execute.side_effect = RuntimeError("sensitive connection details")
    response = client.get(path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable."}


@pytest.mark.parametrize("path", ["/db/estado", "/catalogo/etapas"])
def test_missing_database_is_a_generic_503(monkeypatch, path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable."}


def test_new_routes_do_not_accept_writes(read_client):
    client, _ = read_client
    assert client.post("/db/estado").status_code == 405
    assert client.post("/catalogo/etapas").status_code == 405
