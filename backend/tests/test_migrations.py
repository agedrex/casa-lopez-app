"""Structural revision checks run without PostgreSQL or an installed Alembic."""

import ast
import re
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, MetaData, Table, UniqueConstraint
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
        self.dropped_columns = []
        self.altered_columns = []
        self.dropped_indexes = []
        self.dropped_constraints = []

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
        self.dropped_indexes.append(name)

    def add_column(self, table_name, column, schema):
        self.metadata.tables[f"{schema}.{table_name}"].append_column(column)

    def create_foreign_key(self, name, source_table, referent_table, local_cols, remote_cols, source_schema,
                           referent_schema):
        self.metadata.tables[f"{source_schema}.{source_table}"].append_constraint(ForeignKeyConstraint(
            local_cols, [f"{referent_schema}.{referent_table}.{column}" for column in remote_cols], name=name))

    def create_check_constraint(self, name, table_name, condition, schema):
        self.metadata.tables[f"{schema}.{table_name}"].append_constraint(CheckConstraint(condition, name=name))

    def drop_constraint(self, name, table_name, schema, type_):
        self.dropped_constraints.append(name)
        table = self.metadata.tables.get(f"{schema}.{table_name}")
        if table is not None:  # a dropped CHECK leaves the recorded table, so a later one can replace it
            for constraint in [c for c in table.constraints if c.name == name]:
                table.constraints.discard(constraint)

    def drop_column(self, table_name, column_name, schema):
        self.dropped_columns.append((schema, table_name, column_name))

    def alter_column(self, table_name, column_name, *, schema, nullable, existing_type):
        self.altered_columns.append((schema, table_name, column_name, nullable))
        self.metadata.tables[f"{schema}.{table_name}"].c[column_name].nullable = nullable

    def drop_table(self, name, schema):
        assert schema == "costos"
        self.dropped.append(name)


# Tables created by revisions after 0003, so 0003 neither creates nor drops them.
ADDED_AFTER_DER_V3 = {"precio_venta", "proveedor", "documento_proveedor", "producto_reventa", "compra_reventa",
                      "formulario_consumo", "formulario_consumo_linea", "pedido_proveedor", "pedido_linea", "modelo_insumo",
                      "proveedor_producto"}


# 0011 links the existing precio_material to proveedor (created by 0007), so that FK comes after both tables exist.
LINK_ADDED_LATER = ("costos.precio_material", "costos.proveedor.id")


def load_revision(monkeypatch, filename):
    operations = RecordedOperations()
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(op=operations))
    return operations, runpy.run_path(str(VERSIONS / filename))


def test_revision_chain_replaces_v1_with_v3_then_seeds(monkeypatch):
    chain = {}
    for filename in ("0001_esquema_costos.py", "0002_semillas.py", "0003_der_v3.py", "0004_semillas_v3.py",
                     "0005_gasto_reemplaza_a.py", "0006_precio_venta.py", "0007_proveedores_documentos.py",
                     "0008_reventa.py", "0009_gasto_anulado.py", "0010_compra_sin_unidades.py",
                     "0011_precio_material_proveedor.py", "0012_impuesto_activo.py",
                     "0013_impuestos_vacios.py", "0014_gastos_venta_pct.py",
                     "0015_precio_venta_margen.py", "0016_formulario_consumo.py", "0017_formulario_modelo.py",
                     "0018_pedidos_proveedor.py", "0019_modelo_insumo.py", "0020_proveedor_producto.py"):
        _, revision = load_revision(monkeypatch, filename)
        chain[revision["revision"]] = revision["down_revision"]
    assert chain == {
        "0001_esquema_costos": None, "0002_semillas": "0001_esquema_costos",
        "0003_der_v3": "0002_semillas", "0004_semillas_v3": "0003_der_v3",
        "0005_gasto_reemplaza_a": "0004_semillas_v3", "0006_precio_venta": "0005_gasto_reemplaza_a",
        "0007_proveedores_documentos": "0006_precio_venta", "0008_reventa": "0007_proveedores_documentos",
        "0009_gasto_anulado": "0008_reventa", "0010_compra_sin_unidades": "0009_gasto_anulado",
        "0011_precio_material_proveedor": "0010_compra_sin_unidades",
        "0012_impuesto_activo": "0011_precio_material_proveedor",
        "0013_impuestos_vacios": "0012_impuesto_activo",
        "0014_gastos_venta_pct": "0013_impuestos_vacios",
        "0015_precio_venta_margen": "0014_gastos_venta_pct",
        "0016_formulario_consumo": "0015_precio_venta_margen",
        "0017_formulario_modelo": "0016_formulario_consumo",
        "0018_pedidos_proveedor": "0017_formulario_modelo",
        "0019_modelo_insumo": "0018_pedidos_proveedor",
        "0020_proveedor_producto": "0019_modelo_insumo",
    }


def test_the_selling_expense_revision_adds_one_unconfirmed_parameter_at_zero_and_downgrade_removes_only_it(monkeypatch):
    operations, revision = load_revision(monkeypatch, "0014_gastos_venta_pct.py")
    revision["upgrade"]()
    revision["downgrade"]()
    insercion, borrado = (str(sentencia) for sentencia in operations.executed)
    assert "INSERT INTO costos.parametro" in insercion and "'GASTOS_VENTA_PCT'" in insercion
    assert "'Propuesta, a confirmar con Robert'" in insercion and "ON CONFLICT (codigo) DO NOTHING" in insercion
    assert "'Gastos variables de venta', 0, NULL, '%'" in insercion  # starts at 0: no scenario number moves
    assert borrado == "DELETE FROM costos.parametro WHERE codigo = 'GASTOS_VENTA_PCT'"


def test_der_v3_revision_matches_orm_and_reverses_dependencies(monkeypatch):
    operations, revision = load_revision(monkeypatch, "0003_der_v3.py")
    revision["upgrade"]()
    # The ORM also carries what 0005 to 0012 add on top of DER v3 (gasto_periodo.reemplaza_a_id, precio_venta,
    # proveedor, documento_proveedor, the resale tables, gasto_periodo.anulado and precio_material.proveedor_id, then precio_venta.margen from 0015 the consumption form tables from 0016, the supplier orders from 0018 and `modelo_insumo` from 0019).
    runpy.run_path(str(VERSIONS / "0005_gasto_reemplaza_a.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0006_precio_venta.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0007_proveedores_documentos.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0008_reventa.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0009_gasto_anulado.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0010_compra_sin_unidades.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0011_precio_material_proveedor.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0012_impuesto_activo.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0013_impuestos_vacios.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0015_precio_venta_margen.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0016_formulario_consumo.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0017_formulario_modelo.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0018_pedidos_proveedor.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0019_modelo_insumo.py"))["upgrade"]()
    runpy.run_path(str(VERSIONS / "0020_proveedor_producto.py"))["upgrade"]()
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
            if fk.target_fullname.rsplit(".", 1)[0] != key and (key, fk.target_fullname) != LINK_ADDED_LATER:
                assert created.index(fk.target_fullname.rsplit(".", 1)[0]) < created.index(key)
    revision["downgrade"]()
    assert sorted(operations.dropped) == sorted(
        table.name for table in Base.metadata.tables.values() if table.name not in ADDED_AFTER_DER_V3)


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
        if table.name in ADDED_AFTER_DER_V3:
            continue
        for fk in table.foreign_keys:
            parent = fk.target_fullname.split(".")[1]
            if parent != table.name and parent not in ADDED_AFTER_DER_V3:  # precio_material -> proveedor is 0011's
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


def test_gasto_reemplaza_a_revision_adds_the_column_fk_and_partial_unique_index_and_reverses_them(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0005_gasto_reemplaza_a.py"))  # same recorder: alembic.op is still patched
    assert revision["revision"] == "0005_gasto_reemplaza_a" and revision["down_revision"] == "0004_semillas_v3"
    revision["upgrade"]()
    gasto = operations.metadata.tables["costos.gasto_periodo"]
    column = gasto.c.reemplaza_a_id
    assert column.nullable and str(column.type) == "BIGINT"
    assert {fk.target_fullname for fk in column.foreign_keys} == {"costos.gasto_periodo.id"}
    index = next(i for i in gasto.indexes if i.name == "gasto_periodo_reemplaza_a_uq")
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect())).lower()
    assert "unique" in ddl and "reemplaza_a_id is not null" in ddl
    revision["downgrade"]()
    assert operations.dropped_indexes == ["gasto_periodo_reemplaza_a_uq"]
    assert operations.dropped_constraints == ["fk_gasto_periodo_reemplaza_a_id_gasto_periodo"]
    assert operations.dropped_columns == [("costos", "gasto_periodo", "reemplaza_a_id")]


def test_precio_venta_revision_creates_an_append_only_price_table_and_drops_it(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0006_precio_venta.py"))
    assert revision["revision"] == "0006_precio_venta" and revision["down_revision"] == "0005_gasto_reemplaza_a"
    revision["upgrade"]()
    precio = operations.metadata.tables["costos.precio_venta"]
    assert set(precio.c.keys()) == {"id", "created_at", "producto_id", "precio_ars", "vigente_desde", "creado_por", "nota"}
    assert {fk.target_fullname for fk in precio.foreign_keys} == {"costos.producto.id"}
    revision["downgrade"]()
    assert "precio_venta" in operations.dropped


def test_proveedores_documentos_revision_creates_both_tables_parent_first_and_drops_them_child_first(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0007_proveedores_documentos.py"))
    assert revision["revision"] == "0007_proveedores_documentos" and revision["down_revision"] == "0006_precio_venta"
    revision["upgrade"]()
    created = list(operations.metadata.tables)
    assert created.index("costos.proveedor") < created.index("costos.documento_proveedor")
    proveedor = operations.metadata.tables["costos.proveedor"]
    documento = operations.metadata.tables["costos.documento_proveedor"]
    assert set(proveedor.c.keys()) == {"id", "created_at", "codigo", "nombre", "cuit", "contacto", "telefono",
                                       "direccion", "nota", "activo"}
    assert {fk.target_fullname for fk in documento.foreign_keys} == {"costos.proveedor.id"}
    assert "contenido" in documento.c and "ocr_sugerencia" in documento.c
    assert any(i.name == "proveedor_nombre_uq" and i.unique for i in proveedor.indexes)
    revision["downgrade"]()
    assert operations.dropped[-2:] == ["documento_proveedor", "proveedor"]
    assert "files" in revision["__doc__"] or "documents" in revision["__doc__"]  # the downgrade warns about data loss


def test_reventa_revision_creates_both_tables_parent_first_and_drops_them_child_first(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0008_reventa.py"))
    assert revision["revision"] == "0008_reventa" and revision["down_revision"] == "0007_proveedores_documentos"
    revision["upgrade"]()
    created = list(operations.metadata.tables)
    assert created.index("costos.producto_reventa") < created.index("costos.compra_reventa")
    compra = operations.metadata.tables["costos.compra_reventa"]
    assert {fk.target_fullname for fk in compra.foreign_keys} == {"costos.producto_reventa.id"}
    revision["downgrade"]()
    assert operations.dropped[-2:] == ["compra_reventa", "producto_reventa"]
    assert "lost" in revision["__doc__"]  # the downgrade warns about data loss


def test_gasto_anulado_revision_adds_a_not_null_flag_defaulting_to_false_and_reverses_it(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0009_gasto_anulado.py"))
    assert revision["revision"] == "0009_gasto_anulado" and revision["down_revision"] == "0008_reventa"
    revision["upgrade"]()
    column = operations.metadata.tables["costos.gasto_periodo"].c.anulado
    assert column.nullable is False and str(column.type.compile(dialect=postgresql.dialect())) == "BOOLEAN"
    assert str(column.server_default.arg) == "false"
    revision["downgrade"]()
    assert operations.dropped_columns == [("costos", "gasto_periodo", "anulado")]
    assert "annul" in revision["__doc__"]  # the downgrade warns that annulled rows count again


def test_compra_sin_unidades_revision_makes_units_nullable_and_reverses_it(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    runpy.run_path(str(VERSIONS / "0008_reventa.py"))["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0010_compra_sin_unidades.py"))
    assert revision["revision"] == "0010_compra_sin_unidades" and revision["down_revision"] == "0009_gasto_anulado"
    revision["upgrade"]()
    assert operations.altered_columns == [("costos", "compra_reventa", "unidades", True)]
    revision["downgrade"]()
    assert operations.altered_columns[-1] == ("costos", "compra_reventa", "unidades", False)
    assert "fails" in revision["__doc__"]  # the downgrade warns that price-only rows block it


def test_precio_material_proveedor_revision_adds_a_nullable_link_keeps_the_text_and_reverses_it(monkeypatch):
    operations, base = load_revision(monkeypatch, "0003_der_v3.py")
    base["upgrade"]()
    runpy.run_path(str(VERSIONS / "0007_proveedores_documentos.py"))["upgrade"]()
    revision = runpy.run_path(str(VERSIONS / "0011_precio_material_proveedor.py"))
    assert revision["revision"] == "0011_precio_material_proveedor"
    assert revision["down_revision"] == "0010_compra_sin_unidades"
    revision["upgrade"]()
    precio = operations.metadata.tables["costos.precio_material"]
    assert precio.c.proveedor_id.nullable and "proveedor" in precio.c  # the text column is untouched
    assert {fk.target_fullname for fk in precio.c.proveedor_id.foreign_keys} == {"costos.proveedor.id"}
    assert any(i.name == "ix_precio_material_proveedor_id" for i in precio.indexes)
    # The backfill links only an exact supplier code and never overwrites an existing link.
    (backfill,) = [s for s in operations.executed if "UPDATE costos.precio_material" in s]
    assert "pm.proveedor = p.codigo" in backfill and "pm.proveedor_id IS NULL" in backfill
    assert "DELETE" not in backfill and "nombre" not in backfill
    revision["downgrade"]()
    assert operations.dropped_indexes == ["ix_precio_material_proveedor_id"]
    assert operations.dropped_constraints == ["fk_precio_material_proveedor_id_proveedor"]
    assert operations.dropped_columns == [("costos", "precio_material", "proveedor_id")]
    assert "links" in revision["__doc__"]  # the downgrade warns that the links are lost
