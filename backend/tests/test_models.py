from sqlalchemy import Float, Numeric
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql

from backend.models import Base


EXPECTED_TABLES = {
    "categoria", "producto", "etapa", "material", "proveedor",
    "precio_material", "tipo_cambio", "parametro", "cotizacion",
    "cotizacion_linea", "marca_calidad",
}


def test_phase_one_metadata_has_exact_tables_and_schema():
    assert {table.name for table in Base.metadata.tables.values()} == EXPECTED_TABLES
    assert Base.metadata.schema == "costos"
    assert all(table.schema == "costos" for table in Base.metadata.tables.values())


def test_identity_timestamps_precision_and_foreign_keys():
    for table in Base.metadata.tables.values():
        assert table.c.id.identity.always is True
        assert table.c.created_at.type.timezone is True
        assert table.c.created_at.nullable is False
        assert table.c.created_at.server_default is not None
        assert not any(isinstance(column.type, Float) for column in table.columns)
        for column in table.columns:
            if isinstance(column.type, Numeric):
                assert column.type.asdecimal is True
        for constraint in table.constraints:
            assert constraint.name is not None
        for fk in table.foreign_keys:
            assert fk.target_fullname.startswith("costos.")
            assert fk.ondelete is None
    product = Base.metadata.tables["costos.producto"]
    assert product.c.updated_at.type.timezone is True
    assert product.c.updated_at.onupdate is not None
    assert product.c.codigo_modelo.unique is not True
    assert not any(index.unique for index in product.indexes if product.c.codigo_modelo in index.columns.values())
    assert all("updated_at" not in table.c for table in Base.metadata.tables.values() if table.name != "producto")


def test_postgresql_ddl_has_expression_partial_and_line_indexes():
    indexes = {index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
               for table in Base.metadata.tables.values() for index in table.indexes}
    assert "coalesce(proveedor_id, 0)" in indexes["precio_material_uq"].lower()
    assert "WHERE estado = 'vigente'" in indexes["cotizacion_una_vigente"]
    assert any("(codigo_modelo)" in ddl for ddl in indexes.values())
    assert any("cotizacion_linea" in ddl and "(cotizacion_id)" in ddl for ddl in indexes.values())
    quote = Base.metadata.tables["costos.cotizacion"]
    ddl = str(CreateTable(quote).compile(dialect=postgresql.dialect()))
    assert "costos_calculados" in ddl
    assert "costo_ars IS NOT NULL" in ddl
    assert "JSONB" in ddl


def test_material_has_no_supplier_or_currency_and_line_quantity_is_nullable():
    material = Base.metadata.tables["costos.material"]
    assert "proveedor_id" not in material.c and "moneda" not in material.c
    line = Base.metadata.tables["costos.cotizacion_linea"]
    assert line.c.cantidad.nullable
    assert (line.c.cantidad.type.precision, line.c.cantidad.type.scale) == (10, 4)
    assert line.c.moneda.type.length == 3
