"""GET /api/health is the Railway healthcheck: public, real (it asks the database) and silent about internals."""

import threading
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend import database, db_check
from backend.main import app

UNAVAILABLE = {"status": "unavailable"}
# Anything that must never reach an unauthenticated caller.
LEAKS = ("demo", "mode", "alembic", "revision", "tablas", "host", "password", "secret", "psycopg", "refused")


class FakeResult:
    def scalar_one(self):
        return 1


class FakeConnection:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        self.engine.opened += 1
        return self

    def __exit__(self, *exc):
        self.engine.closed += 1
        return False

    def execute(self, statement, *args, **kwargs):
        self.engine.statements.append(str(statement))
        if self.engine.failure is not None:
            raise self.engine.failure
        if self.engine.gate is not None:
            self.engine.gate.wait()
        return FakeResult()


class FakeEngine:
    """Stands in for the SQLAlchemy engine of the app: counts opened / closed connections."""

    def __init__(self, failure=None, gate=None):
        self.failure, self.gate = failure, gate
        self.opened = self.closed = 0
        self.statements = []
        self.disposed = False

    def connect(self):
        return FakeConnection(self)

    def dispose(self):
        self.disposed = True


@contextmanager
def client_with(monkeypatch, engine):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.internal.example:5432/costos")
    monkeypatch.setattr(database, "create_database_engine", lambda: engine)
    with TestClient(app) as client:
        yield client


def assert_silent(response):
    body = response.text.lower()
    assert not any(word in body for word in LEAKS), response.text


def test_healthy_database_answers_200_with_only_the_status(monkeypatch):
    engine = FakeEngine()
    with client_with(monkeypatch, engine) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert any("SELECT 1" in statement for statement in engine.statements)
    assert engine.opened == engine.closed == 1  # the connection is returned, not left open


def test_health_is_public(monkeypatch):
    with client_with(monkeypatch, FakeEngine()) as client:
        assert client.get("/api/health").status_code == 200  # no session, no verifier configured


def test_missing_database_url_answers_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert_silent(response)


def test_failing_query_answers_503_without_the_error_text(monkeypatch):
    engine = FakeEngine(failure=RuntimeError("connection to db.internal.example refused, password=secret"))
    with client_with(monkeypatch, engine) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert_silent(response)
    assert engine.opened == engine.closed == 1


def test_unreachable_database_answers_503_with_a_real_engine(monkeypatch):
    # Port 1 refuses at once: the real engine and the real driver fail, and nothing of that reaches the caller.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:1/costos")
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert_silent(response)


def test_a_database_that_hangs_does_not_hang_the_request(monkeypatch):
    gate = threading.Event()
    engine = FakeEngine(gate=gate)
    monkeypatch.setattr(db_check, "HEALTH_TIMEOUT_SECONDS", 0.2)
    try:
        with client_with(monkeypatch, engine) as client:
            started = time.monotonic()
            response = client.get("/api/health")
            elapsed = time.monotonic() - started
        assert response.status_code == 503
        assert response.json() == UNAVAILABLE
        assert elapsed < 2
    finally:
        gate.set()  # let the probe thread finish and close its connection
    deadline = time.monotonic() + 2
    while engine.closed < engine.opened and time.monotonic() < deadline:
        time.sleep(0.01)
    assert engine.opened == engine.closed == 1


def test_the_default_timeout_is_short():
    assert 0 < db_check.HEALTH_TIMEOUT_SECONDS <= 3


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_health_does_not_accept_writes(monkeypatch, method):
    with client_with(monkeypatch, FakeEngine()) as client:
        assert getattr(client, method)("/api/health").status_code == 405


def test_health_against_a_real_postgres(local_postgres, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", local_postgres.url.render_as_string(hide_password=False))
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
