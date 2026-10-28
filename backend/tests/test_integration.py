"""Run only against an explicitly configured disposable local PostgreSQL."""

import runpy
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.db_verification import (
    PROBE_NAMES, SEED_COUNTS, inspect_database, prepare_probe_data, run_write_probe,
)
from backend.models import Base


@pytest.mark.parametrize("number", range(1, len(PROBE_NAMES) + 2))
def test_postgresql_constraints_and_seeds(local_postgres, number):
    with local_postgres.connect() as connection:
        transaction = connection.begin()
        try:
            if number == len(PROBE_NAMES) + 1:
                assert inspect_database(connection)["seeds_valid"]
            else:
                data = prepare_probe_data(connection)
                assert run_write_probe(connection, number, data), f"Constraint probe {number} failed."
        finally:
            transaction.rollback()


def test_head_has_exactly_the_v3_tables_and_seed_counts(local_postgres):
    with local_postgres.connect() as connection:
        result = inspect_database(connection)
        assert result["revision"] == "0004_semillas_v3"
        assert {name.removeprefix("costos.") for name in Base.metadata.tables} == set(result["tables"]) - {"alembic_version"}
        assert result["counts"] == SEED_COUNTS
        assert connection.execute(text("SELECT count(*) FROM costos.producto")).scalar_one() == 0


def execute_seed_downgrade(connection):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0004_semillas_v3.py"
    revision = runpy.run_path(str(path))
    with Operations.context(MigrationContext.configure(connection)):
        revision["downgrade"]()


def test_seed_downgrade_removes_only_the_seeded_rows(local_postgres):
    with local_postgres.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(
                "INSERT INTO costos.categoria (codigo, nombre) VALUES ('CAT-USER', 'Added by a person')"))
            execute_seed_downgrade(connection)
            remaining = connection.execute(text("SELECT codigo FROM costos.categoria")).scalars().all()
            assert remaining == ["CAT-USER"]
            for name in ("etapa", "material", "modelo", "tipo_cambio", "precio_material", "gasto_periodo"):
                assert connection.execute(text(f"SELECT count(*) FROM costos.{name}")).scalar_one() == 0
        finally:
            transaction.rollback()
