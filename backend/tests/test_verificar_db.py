from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

from backend import verificar_db
from backend.db_verification import expect_constraint
from sqlalchemy.exc import IntegrityError
from pathlib import Path
from decimal import Decimal
from datetime import date
import re


def exact_sql_seed_fixture():
    """Decode literal VALUES rows from the unchanged SQL source, without executing SQL."""
    source = (Path(__file__).parents[2] / "docs" / "der-borrador.sql").read_text(encoding="utf-8")
    source = source.split("-- ---------- Datos semilla (los del Excel) ----------")[1].split("COMMIT;")[0]
    data = {}
    for statement in source.split(";"):
        if not statement.strip():
            continue
        name = re.search(r"INSERT INTO (\w+)", statement).group(1)
        literals = statement.split("VALUES", 1)[1].split(") AS v", 1)[0]
        tokens = re.findall(r"'(?:''|[^'])*'|\(|\)|,|NULL|true|false|\d+(?:\.\d+)?", literals)
        rows = []
        row = None
        for token in tokens:
            if token == "(":
                row = []
            elif token == ")":
                if row is not None:
                    rows.append(tuple(row))
                    row = None
            elif token != "," and row is not None:
                if token.startswith("'"):
                    value = token[1:-1].replace("''", "'")
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        value = date.fromisoformat(value)
                elif token == "NULL":
                    value = None
                elif token in ("true", "false"):
                    value = token == "true"
                else:
                    value = Decimal(token)
                row.append(value)
        if name == "material":
            rows = [row + (True,) for row in rows]
        elif name == "proveedor":
            rows = [row + (None, None, None, None, None, True) for row in rows]
        elif name == "precio_material":
            rows = [row[:-1] + ("excel_migracion", row[-1]) for row in rows]
        elif name == "parametro":
            rows = [row[:3] + ("supuesto",) + row[3:] for row in rows]
        elif name == "categoria":
            rows = [row + (True,) for row in rows]
        data[name] = rows
    return data


@pytest.mark.parametrize("table, natural_key, field, value", [
    ("precio_material", "cuero:5", 2, Decimal("1")),
    ("tipo_cambio", date(2026, 9, 1), 1, Decimal("1")),
    ("parametro", "GANANCIA_PCT", 1, Decimal("50")),
    ("etapa", "CUERO", 1, "Wrong stage definition"),
])
def test_exact_seed_validation_rejects_same_count_corruption(table, natural_key, field, value):
    from backend.db_verification import seed_rows_match
    rows = exact_sql_seed_fixture()
    assert seed_rows_match(rows)
    changed = list(rows[table])
    index = next(index for index, row in enumerate(changed) if row[0] == natural_key)
    replacement = list(changed[index])
    replacement[field] = value
    changed[index] = tuple(replacement)
    rows[table] = changed
    assert not seed_rows_match(rows)


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
        "revision": "0002_semillas", "tables": sorted(verificar_db.DOMAIN_TABLES),
        "counts": verificar_db.SEED_COUNTS, "seeds_valid": True,
    })
    probes = MagicMock(return_value=[(str(index), True) for index in range(1, 13)])
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
        "revision": "0002_semillas", "tables": sorted(verificar_db.DOMAIN_TABLES),
        "counts": verificar_db.SEED_COUNTS, "seeds_valid": True,
    })
    assert verificar_db.main([]) == 1
