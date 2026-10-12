"""Run only against an explicitly configured disposable local PostgreSQL."""

import os
import runpy
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url

from backend.db_verification import (
    inspect_database, prepare_probe_data, run_write_probe,
)
from backend.models import Material, PrecioMaterial, Proveedor


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


@pytest.mark.parametrize("number", range(1, 14))
def test_postgresql_constraints_and_seeds(local_postgres, number):
    with local_postgres.connect() as connection:
        transaction = connection.begin()
        try:
            if number == 13:
                assert inspect_database(connection)["seeds_valid"]
            else:
                data = prepare_probe_data(connection)
                assert run_write_probe(connection, number, data), f"Constraint probe {number} failed."
        finally:
            transaction.rollback()


def execute_seed_downgrade(connection):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0002_semillas.py"
    revision = runpy.run_path(str(path))
    with Operations.context(MigrationContext.configure(connection)):
        revision["downgrade"]()


def test_seed_downgrade_preserves_unrelated_same_name_supplier(local_postgres):
    with local_postgres.connect() as connection:
        transaction = connection.begin()
        try:
            unrelated_id = connection.execute(insert(Proveedor).values(
                nombre="Rouez", categorias="refuerzos", cuit="20-00000000-0", contacto="Unrelated supplier"
            ).returning(Proveedor.id)).scalar_one()
            execute_seed_downgrade(connection)
            assert connection.execute(select(Proveedor.id)).scalars().all() == [unrelated_id]
            assert connection.execute(select(Proveedor.contacto)).scalar_one() == "Unrelated supplier"
        finally:
            transaction.rollback()


def test_seed_downgrade_refuses_ambiguous_linked_supplier(local_postgres):
    with local_postgres.connect() as connection:
        transaction = connection.begin()
        try:
            original = connection.execute(select(PrecioMaterial.__table__).join(
                Material, PrecioMaterial.material_id == Material.id
            ).where(Material.codigo_excel == "insumo:W5")).mappings().one()
            duplicate_supplier = connection.execute(insert(Proveedor).values(
                nombre="Rouez", categorias="refuerzos"
            ).returning(Proveedor.id)).scalar_one()
            copied = {key: value for key, value in original.items() if key not in {"id", "created_at"}}
            copied["proveedor_id"] = duplicate_supplier
            connection.execute(insert(PrecioMaterial).values(**copied))
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(DBAPIError, match="Seed supplier identity is missing or ambiguous"):
                    execute_seed_downgrade(connection)
            finally:
                savepoint.rollback()
            # The guard runs before any seed deletion, preserving every original row.
            assert len(connection.execute(select(Proveedor.id)).all()) == 3
            assert len(connection.execute(select(PrecioMaterial.id)).all()) == 12
        finally:
            transaction.rollback()
