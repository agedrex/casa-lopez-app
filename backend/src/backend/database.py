"""PostgreSQL configuration and request-scoped SQLAlchemy sessions."""

import os
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session


class DatabaseConfigurationError(RuntimeError):
    """A database configuration error with a safe, fixed message."""


def get_database_url() -> URL:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required for database access."
        ) from None
    try:
        url = make_url(raw_url)
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ValueError
        if not url.host or not url.database:
            raise ValueError
        return url.set(drivername="postgresql+psycopg")
    except Exception:
        raise DatabaseConfigurationError(
            "DATABASE_URL must be a valid PostgreSQL URL using psycopg."
        ) from None


def create_database_engine() -> Engine:
    url = get_database_url()
    try:
        # SQLAlchemy connects lazily; no network operation happens here.
        return create_engine(
            url, pool_pre_ping=True, hide_parameters=True, echo=False,
            connect_args={"connect_timeout": 10},
        )
    except Exception:
        raise DatabaseConfigurationError(
            "Database engine initialization failed."
        ) from None


def get_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.db_engine
    if engine is None:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required for database access."
        ) from None
    # Closing rolls back any uncommitted transaction. Call commit explicitly.
    with Session(engine) as session:
        yield session
