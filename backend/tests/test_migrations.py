"""Structural revision checks run without PostgreSQL or an installed Alembic."""

import ast
import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import CheckConstraint, Index, MetaData, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from backend.models import Base


BACKEND = Path(__file__).parents[1]
VERSIONS = BACKEND / "migrations" / "versions"


class RecordedOperations:
    """Record declared migration operations; this is not an Alembic runtime."""
    def __init__(self):
        self.metadata = MetaData()
        self.dropped = []
        self.executed = []

    def f(self, name):
        return name

    def execute(self, statement):
        self.executed.append(statement)

    def create_table(self, name, *elements, schema):
        Table(name, self.metadata, *elements, schema=schema)

    def create_index(self, name, table_name, columns, schema, **kwargs):
        table = self.metadata.tables[f"{schema}.{table_name}"]
        expressions = [table.c[col] if isinstance(col, str) else col for col in columns]
        index = Index(name, *expressions, **kwargs)
        if index.table is None:
            table.append_constraint(index)

    def drop_index(self, name, **kwargs):
        pass

    def drop_table(self, name, schema):
        assert schema == "costos"
        self.dropped.append(name)


def load_revision(monkeypatch, filename):
    operations = RecordedOperations()
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(op=operations))
    return operations, runpy.run_path(str(VERSIONS / filename))


def test_revision_chain_replaces_v1_with_v3_then_seeds(monkeypatch):
    chain = {}
    for filename in ("0001_esquema_costos.py", "0002_semillas.py", "0003_der_v3.py", "0004_semillas_v3.py"):
        _, revision = load_revision(monkeypatch, filename)
        chain[revision["revision"]] = revision["down_revision"]
    assert chain == {
        "0001_esquema_costos": None, "0002_semillas": "0001_esquema_costos",
        "0003_der_v3": "0002_semillas", "0004_semillas_v3": "0003_der_v3",
    }


def test_der_v3_revision_matches_orm_and_reverses_dependencies(monkeypatch):
    operations, revision = load_revision(monkeypatch, "0003_der_v3.py")
    revision["upgrade"]()
    assert set(operations.metadata.tables) == set(Base.metadata.tables)
    dialect = postgresql.dialect()
    for key, declared in operations.metadata.tables.items():
        model = Base.metadata.tables[key]
        assert set(declared.c.keys()) == set(model.c.keys())
        for name, column in declared.c.items():
            expected = model.c[name]
            assert str(column.type.compile(dialect=dialect)) == str(expected.type.compile(dialect=dialect))
            assert column.nullable == expected.nullable
            assert (column.identity.always if column.identity else None) == (expected.identity.always if expected.identity else None)
            if column.server_default and not column.identity:
                assert str(column.server_default.arg) == str(expected.server_default.arg)
        assert {constraint.name for constraint in declared.constraints} == {constraint.name for constraint in model.constraints}
        assert {constraint.name: str(constraint.sqltext) for constraint in declared.constraints if isinstance(constraint, CheckConstraint)} == {
            constraint.name: str(constraint.sqltext) for constraint in model.constraints if isinstance(constraint, CheckConstraint)}
        assert {constraint.name: tuple(constraint.columns.keys()) for constraint in declared.constraints if isinstance(constraint, UniqueConstraint)} == {
            constraint.name: tuple(constraint.columns.keys()) for constraint in model.constraints if isinstance(constraint, UniqueConstraint)}
        assert {fk.target_fullname for fk in declared.foreign_keys} == {fk.target_fullname for fk in model.foreign_keys}
        assert {index.name: str(CreateIndex(index).compile(dialect=dialect)).lower() for index in declared.indexes} == {
            index.name: str(CreateIndex(index).compile(dialect=dialect)).lower() for index in model.indexes}
    # Parents are created before the tables that reference them.
    created = list(operations.metadata.tables)
    for key, declared in operations.metadata.tables.items():
        for fk in declared.foreign_keys:
            if fk.target_fullname.rsplit(".", 1)[0] != key:
                assert created.index(fk.target_fullname.rsplit(".", 1)[0]) < created.index(key)
    revision["downgrade"]()
    assert sorted(operations.dropped) == sorted(table.name for table in Base.metadata.tables.values())


def test_der_v3_upgrade_drops_only_v1_tables_in_costos_with_if_exists(monkeypatch):
    operations, revision = load_revision(monkeypatch, "0003_der_v3.py")
    revision["upgrade"]()
    assert len(operations.executed) == 11
    for statement in operations.executed:
        assert re.fullmatch(r"DROP TABLE IF EXISTS costos\.[a-z_]+ CASCADE", statement)
    dropped = {statement.split("costos.")[1].split()[0] for statement in operations.executed}
    assert dropped == {"categoria", "producto", "etapa", "material", "proveedor", "precio_material", "tipo_cambio",
                       "parametro", "cotizacion", "cotizacion_linea", "marca_calidad"}
    assert "alembic_version" not in "".join(operations.executed) and "public." not in "".join(operations.executed)


def test_der_v3_downgrade_drops_children_before_parents_and_documents_v1_is_gone(monkeypatch):
    operations, revision = load_revision(monkeypatch, "0003_der_v3.py")
    revision["downgrade"]()
    position = {name: index for index, name in enumerate(operations.dropped)}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            parent = fk.target_fullname.split(".")[1]
            if parent != table.name:
                assert position[table.name] < position[parent]
    assert "not supported" in revision["__doc__"] or "not recreated" in revision["__doc__"]


def test_seed_revision_is_exact_sql_source_with_explicit_schema():
    module = ast.parse((VERSIONS / "0002_semillas.py").read_text(encoding="utf-8"))
    assigned = {node.targets[0].id: node.value for node in module.body if isinstance(node, ast.Assign)}
    assert ast.literal_eval(assigned["down_revision"]) == "0001_esquema_costos"
    statements = ast.literal_eval(assigned["SEED_STATEMENTS"])
    source = (BACKEND.parent / "docs" / "der-borrador.sql").read_text(encoding="utf-8")
    source = source.split("-- ---------- Datos semilla (los del Excel) ----------")[1].split("COMMIT;")[0]
    expected = [part.strip() for part in source.split(";") if part.strip()]
    assert len(statements) == 7
    assert [statement.replace("costos.", "") for statement in statements] == expected
    for statement in statements:
        for table in re.findall(r"(?:INSERT INTO|JOIN|FROM) ([a-z_.]+)", statement):
            assert table.startswith("costos.")


def test_alembic_configuration_has_empty_url_and_only_application_schema(monkeypatch):
    ini = (BACKEND / "alembic.ini").read_text(encoding="utf-8")
    assert re.search(r"^sqlalchemy.url\s*=\s*$", ini, re.MULTILINE)
    code = (BACKEND / "migrations" / "env.py").read_text(encoding="utf-8")
    tree = ast.parse(code)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "include_name"]
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "filter", "exec"), namespace)
    include_name = namespace["include_name"]
    assert include_name("costos", "schema", {}) is True
    for schema in ("public", None, "other"):
        assert include_name(schema, "schema", {}) is False
    assert include_name("user", "table", {"schema_name": "public"}) is False
    assert include_name("producto", "table", {"schema_name": "costos"}) is True
    assert 'version_table_schema="costos"' in code
    assert "config.set_main_option" not in code
    assert "CREATE SCHEMA IF NOT EXISTS costos" in code
    assert "connection.commit()" in code


def test_offline_environment_emits_schema_before_migration_transaction(monkeypatch):
    from unittest.mock import MagicMock
    from backend import database
    calls = []
    context = MagicMock()
    context.is_offline_mode.return_value = True
    context.execute.side_effect = lambda sql: calls.append(sql)
    context.begin_transaction.side_effect = lambda: calls.append("begin") or MagicMock()
    context.run_migrations.side_effect = lambda: calls.append("migrations")
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(context=context))
    monkeypatch.setattr(database, "get_database_url", lambda: object())
    runpy.run_path(str(BACKEND / "migrations" / "env.py"))
    assert calls == ["CREATE SCHEMA IF NOT EXISTS costos", "begin", "migrations"]
    kwargs = context.configure.call_args.kwargs
    assert kwargs["version_table_schema"] == "costos"
    assert kwargs["include_schemas"] is True


def test_environment_missing_url_is_safe_and_clear(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    context = MagicMock()
    context.is_offline_mode.return_value = True
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(context=context))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL is required for database access"):
        runpy.run_path(str(BACKEND / "migrations" / "env.py"))


def test_seed_downgrade_captures_suppliers_before_deleting_and_refuses_ambiguity(monkeypatch):
    statements = []
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(op=SimpleNamespace(execute=statements.append)))
    revision = runpy.run_path(str(VERSIONS / "0002_semillas.py"))
    revision["downgrade"]()
    sql = "\n".join(statements)
    assert sql.lstrip().startswith("DO $wo2$")
    assert sql.index("INTO candidate_supplier_ids") < sql.index("DELETE FROM costos.precio_material")
    assert "RAISE EXCEPTION" in sql
    assert "cardinality(candidate_supplier_ids)" in sql
    assert "id = ANY(captured_supplier_ids)" in sql
    assert "p.cuit IS NULL" in sql and "p.contacto IS NULL" in sql
    assert "DELETE FROM costos.proveedor WHERE nombre IN" not in sql
