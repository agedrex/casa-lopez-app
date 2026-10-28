from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

from backend import verificar_db
from backend.db_verification import expect_constraint
from sqlalchemy.exc import IntegrityError


SEED_CODES = {
    "etapa": ["CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION"],
    "material": ["MAT-CU01", "MAT-CU02", "MAT-CU03", "MAT-CU04", "MAT-CU05", "MAT-CU06", "MAT-FO01",
                 "MAT-FO02", "MAT-FL01", "MAT-GE01", "MAT-HE00", "MAT-HC01", "MAT-CA01"],
    "persona": [f"PER-000{number}" for number in range(1, 8)],
}


def test_seed_validation_accepts_the_expected_business_keys():
    from backend.db_verification import seed_rows_match
    assert seed_rows_match(SEED_CODES, ["MAT-CU03", "MAT-CU04"])


@pytest.mark.parametrize("table, replacement", [
    ("etapa", "REB"), ("material", "MAT-CU99"), ("persona", "PER-0099"),
])
def test_seed_validation_rejects_same_count_corruption(table, replacement):
    from backend.db_verification import seed_rows_match
    codes = {name: list(values) for name, values in SEED_CODES.items()}
    codes[table][0] = replacement
    assert not seed_rows_match(codes, ["MAT-CU03", "MAT-CU04"])


def test_seed_validation_rejects_duplicates_and_unblocked_exotics():
    from backend.db_verification import seed_rows_match
    codes = {name: list(values) for name, values in SEED_CODES.items()}
    codes["etapa"][1] = "CUERO"
    assert not seed_rows_match(codes, ["MAT-CU03", "MAT-CU04"])
    assert not seed_rows_match(SEED_CODES, ["MAT-CU03"])


def test_expected_seed_counts_cover_the_seeded_tables():
    assert verificar_db.SEED_COUNTS["etapa"] == 8 and verificar_db.SEED_COUNTS["material"] == 13
    assert verificar_db.SEED_COUNTS["modelo"] == 325
    assert set(verificar_db.SEED_COUNTS) <= verificar_db.DOMAIN_TABLES
    assert len(verificar_db.DOMAIN_TABLES) == 25


@pytest.mark.parametrize("environment", ["production", "proto", "", "STAGING"])
def test_non_staging_railway_environment_refuses_before_connect(monkeypatch, capsys, environment):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", environment)
    create = MagicMock()
    monkeypatch.setattr(verificar_db, "create_database_engine", create)
    assert verificar_db.main([]) == 1
    create.assert_not_called()
    assert "FALLA" in capsys.readouterr().out


def test_connection_errors_have_fixed_output(monkeypatch, capsys):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.setattr(verificar_db, "create_database_engine", MagicMock(side_effect=RuntimeError("sensitive details")))
    assert verificar_db.main([]) == 1
    output = capsys.readouterr().out
    assert "sensitive" not in output
    assert "FALLA" in output


@pytest.mark.parametrize("probe_fails", [False, True])
def test_write_verification_always_rolls_back_one_outer_transaction(monkeypatch, capsys, probe_fails):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    transaction = connection.begin.return_value
    monkeypatch.setattr(verificar_db, "create_database_engine", lambda: engine)
    monkeypatch.setattr(verificar_db, "inspect_database", lambda conn: {
        "revision": "0004_semillas_v3", "tables": sorted(verificar_db.DOMAIN_TABLES),
        "counts": verificar_db.SEED_COUNTS, "seeds_valid": True,
    })
    probes = MagicMock(return_value=[(str(index), True) for index in range(1, 11)])
    if probe_fails:
        probes.side_effect = RuntimeError("sensitive details")
    monkeypatch.setattr(verificar_db, "run_write_probes", probes)
    assert verificar_db.main(["--prueba-escritura"]) == (1 if probe_fails else 0)
    connection.begin.assert_called_once()
    transaction.rollback.assert_called_once()
    connection.commit.assert_not_called()
    transaction.commit.assert_not_called()
    engine.dispose.assert_called_once()
    assert "sensitive" not in capsys.readouterr().out


@pytest.mark.parametrize("actual_constraint, expected", [("requested", True), ("unrelated", False)])
def test_probes_verify_the_specific_constraint_and_rollback_savepoint(actual_constraint, expected):
    connection = MagicMock()
    original_error = RuntimeError("hidden driver message")
    original_error.diag = SimpleNamespace(constraint_name=actual_constraint)
    operation = MagicMock(side_effect=IntegrityError(None, None, original_error))
    assert expect_constraint(connection, operation, True, "requested") is expected
    connection.begin_nested.return_value.rollback.assert_called_once()


def test_probe_non_integrity_error_still_rolls_back_savepoint():
    connection = MagicMock()
    operation = MagicMock(side_effect=RuntimeError("failure"))
    with pytest.raises(RuntimeError):
        expect_constraint(connection, operation, True, "requested")
    connection.begin_nested.return_value.rollback.assert_called_once()


def test_cleanup_failure_returns_nonzero(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "staging")
    engine = MagicMock()
    engine.dispose.side_effect = RuntimeError("hidden details")
    monkeypatch.setattr(verificar_db, "create_database_engine", lambda: engine)
    monkeypatch.setattr(verificar_db, "inspect_database", lambda conn: {
        "revision": "0004_semillas_v3", "tables": sorted(verificar_db.DOMAIN_TABLES),
        "counts": verificar_db.SEED_COUNTS, "seeds_valid": True,
    })
    assert verificar_db.main([]) == 1
