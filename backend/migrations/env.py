"""Migrate only the application schema, without exposing connection details."""

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from backend.database import DatabaseConfigurationError, get_database_url
from backend.models import Base


target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == "costos"
    if type_ == "table":
        return parent_names.get("schema_name") == "costos"
    return True


def configure(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema="costos",
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline():
    configure(url=get_database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    # The version table needs this schema before the first revision is run.
    context.execute("CREATE SCHEMA IF NOT EXISTS costos")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(
        get_database_url(), poolclass=NullPool, hide_parameters=True,
        echo=False, connect_args={"connect_timeout": 10},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS costos"))
            connection.commit()
            configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
except DatabaseConfigurationError as error:
    raise SystemExit(str(error)) from None
except Exception:
    raise SystemExit("Database migration failed. Connection details are hidden.") from None
