"""Shared fixtures. PostgreSQL ones skip unless TEST_DATABASE_URL names a disposable local database."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def local_postgres():
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is absent; disposable local PostgreSQL is required.")
    if "RAILWAY_ENVIRONMENT_NAME" in os.environ:
        pytest.fail("Integration tests require disposable local PostgreSQL, outside Railway.")
    try:
        url = make_url(raw_url)
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"} or url.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError
        url = url.set(drivername="postgresql+psycopg")
    except Exception:
        pytest.fail("TEST_DATABASE_URL must identify disposable local PostgreSQL.")
    pytest.importorskip("alembic", reason="Alembic is required to apply local migrations.")
    from alembic import command
    from alembic.config import Config
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("DATABASE_URL", raw_url)
        command.upgrade(config, "head")
    engine = create_engine(url, echo=False, hide_parameters=True, connect_args={"connect_timeout": 10})
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def no_auth_verify_url(monkeypatch):
    """The auth gate must be fail-closed unless a test configures AUTH_VERIFY_URL itself."""
    monkeypatch.delenv("AUTH_VERIFY_URL", raising=False)
