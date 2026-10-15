from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import psycopg
from sqlalchemy import create_engine, text

from backend import database
from backend.main import app, lifespan


@pytest.fixture(autouse=True)
def isolated_database_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_postgresql_urls_preserve_credentials_and_options(monkeypatch, scheme):
    monkeypatch.setenv(
        "DATABASE_URL",
        f"{scheme}://user:p%40ss%2Fword@localhost:5432/example?sslmode=require&application_name=demo",
    )
    url = database.get_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss/word"
    assert url.database == "example"
    assert dict(url.query) == {"sslmode": "require", "application_name": "demo"}


@pytest.mark.parametrize(
    "value",
    [None, "", "not-a-url-secret", "postgresql://user:secret@host:bad/db",
     "postgresql://", "sqlite:///secret.db", "postgresql+asyncpg://user:secret@host/db"],
)
def test_invalid_configuration_is_sanitized(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(database.DatabaseConfigurationError) as error:
        database.get_database_url()
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__


def test_engine_creation_is_lazy_and_uses_safe_options(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@localhost/example")
    connect = MagicMock(side_effect=AssertionError("Network access is forbidden"))
    monkeypatch.setattr(psycopg, "connect", connect)
    create = MagicMock(wraps=create_engine)
    monkeypatch.setattr(database, "create_engine", create)
    engine = database.create_database_engine()
    assert engine.dialect.driver == "psycopg"
    assert create.call_args.kwargs == {
        "pool_pre_ping": True, "hide_parameters": True,
        "echo": False, "connect_args": {"connect_timeout": 10},
    }
    connect.assert_not_called()
    engine.dispose()


@pytest.mark.parametrize("fail", [False, True])
def test_session_closes_and_rolls_back_without_implicit_commit(fail):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE example (value INTEGER)"))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_engine=engine)))
    dependency = database.get_session(request)
    session = next(dependency)
    session.execute(text("INSERT INTO example VALUES (1)"))
    if fail:
        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError("request failed"))
    else:
        with pytest.raises(StopIteration):
            next(dependency)
    assert not session.in_transaction()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM example")) == 0
    engine.dispose()


def test_session_requires_configuration():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_engine=None)))
    with pytest.raises(database.DatabaseConfigurationError, match="DATABASE_URL"):
        next(database.get_session(request))


@pytest.mark.anyio
async def test_lifespan_disposes_engine_after_failure(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@localhost/example")
    engine = MagicMock()
    monkeypatch.setattr(database, "create_database_engine", lambda: engine)
    with pytest.raises(RuntimeError):
        async with lifespan(app):
            assert app.state.db_engine is engine
            engine.connect.assert_not_called()
            raise RuntimeError("application failed")
    engine.dispose.assert_called_once()


@pytest.mark.anyio
async def test_lifespan_supports_demo_without_database():
    async with lifespan(app):
        assert app.state.db_engine is None
