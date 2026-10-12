from unittest.mock import MagicMock

import pytest

from backend import db_check


@pytest.fixture(autouse=True)
def isolated_database_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_check_executes_only_select_one_and_cleans_up(monkeypatch, capsys):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    monkeypatch.setattr(db_check, "create_database_engine", lambda: engine)
    assert db_check.main() == 0
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    connection.execute.assert_called_once()
    engine.connect.return_value.__exit__.assert_called_once()
    engine.dispose.assert_called_once()
    assert capsys.readouterr().out == "Database connection check succeeded.\n"


@pytest.mark.parametrize("stage", ["creation", "connection", "query", "disposal"])
def test_check_failure_suppresses_driver_secrets_and_cleans_up(monkeypatch, capsys, stage):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    create = MagicMock(return_value=engine)
    failing_call = {
        "creation": create, "connection": engine.connect,
        "query": connection.execute, "disposal": engine.dispose,
    }[stage]
    failing_call.side_effect = RuntimeError("postgres://user:secret@host/db")
    monkeypatch.setattr(db_check, "create_database_engine", create)
    assert db_check.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Database connection check failed.\n"
    if stage != "creation":
        engine.dispose.assert_called_once()
    if stage == "query":
        engine.connect.return_value.__exit__.assert_called_once()


def test_check_missing_configuration_is_actionable_and_safe(capsys):
    assert db_check.main() == 1
    assert capsys.readouterr().err == "DATABASE_URL is required for database access.\n"
