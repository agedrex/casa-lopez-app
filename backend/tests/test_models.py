import re

import pytest
from sqlalchemy import CheckConstraint, Float, Numeric, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from backend.models import Base, DocumentoProveedor


EXPECTED_TABLES = {
    "modelo", "producto", "receta_linea", "precio_material", "tipo_cambio", "orden_fabricacion",
    "orden_item", "gasto_periodo", "etapa", "material", "categoria", "color", "persona", "taller",
    "impuesto", "parametro", "molde", "modelo_molde", "orden_estado", "registro_tarea",
    "pieza_cuero", "movimiento_cuero", "conteo_inventario", "kit_componente", "cotizacion", "precio_venta",
    "proveedor", "documento_proveedor", "producto_reventa", "compra_reventa",
}
# Tables whose sheet has a "Código" column: the business key, unique and immutable.
WITH_CODIGO = {
    "modelo", "producto", "receta_linea", "precio_material", "orden_fabricacion", "orden_item",
    "gasto_periodo", "etapa", "material", "categoria", "color", "persona", "taller", "impuesto",
    "parametro", "molde", "pieza_cuero", "proveedor", "producto_reventa",
}
NUMERIC_PRECISIONS = {(14, 4), (12, 6), (12, 4), (6, 3)}


def table(name):
    return Base.metadata.tables[f"costos.{name}"]


def check_text(name):
    return {c.name: str(c.sqltext) for c in table(name).constraints if isinstance(c, CheckConstraint)}


def test_der_v3_plus_proveedores_has_the_30_tables_in_schema_costos():
    assert {t.name for t in Base.metadata.tables.values()} == EXPECTED_TABLES
    assert len(EXPECTED_TABLES) == 30
    assert Base.metadata.schema == "costos"
    assert all(t.schema == "costos" for t in Base.metadata.tables.values())


def test_every_table_has_identity_created_at_and_named_constraints():
    for t in Base.metadata.tables.values():
        assert t.c.id.identity.always is True
        assert t.c.created_at.type.timezone is True
        assert t.c.created_at.nullable is False and t.c.created_at.server_default is not None
        assert all(constraint.name for constraint in t.constraints)
        for fk in t.foreign_keys:
            assert fk.target_fullname.startswith("costos.")
            assert fk.ondelete is None


@pytest.mark.parametrize("name", sorted(EXPECTED_TABLES))
def test_codigo_is_a_unique_text_business_key_exactly_where_the_sheet_has_it(name):
    t = table(name)
    if name not in WITH_CODIGO:
        assert "codigo" not in t.c
        return
    assert t.c.codigo.nullable is False
    unique_columns = [tuple(c.columns.keys()) for c in t.constraints if isinstance(c, UniqueConstraint)]
    assert ("codigo",) in unique_columns


def test_money_is_numeric_with_decimals_never_float():
    for t in Base.metadata.tables.values():
        for column in t.columns:
            assert not isinstance(column.type, Float), f"{t.name}.{column.name}"
            if isinstance(column.type, Numeric):
                assert column.type.asdecimal is True
                assert (column.type.precision, column.type.scale) in NUMERIC_PRECISIONS, f"{t.name}.{column.name}"
    assert table("cotizacion").c.total_ars.type.precision == 14
    assert table("tipo_cambio").c.ars_por_usd.type.precision == 12
    assert table("modelo").c.cuero_m2_por_unidad.type.scale == 6
    assert table("impuesto").c.alicuota.type.scale == 3


@pytest.mark.parametrize("name, constraint, values", [
    ("producto", "ck_producto_estado_del_ciclo", ["EN_DEFINICION", "COTIZADO", "EN_PRODUCCION", "PRODUCIDO"]),
    ("producto", "ck_producto_quien_lo_confecciona", ["EXTERNA", "INTERNA"]),
    ("modelo", "ck_modelo_tamano", ["CHICO", "MEDIANO", "GRANDE"]),
    ("modelo", "ck_modelo_origen_de_los_consumos", ["EXCEL", "MOLDE", "ESTIMADO", "MEDIDO"]),
    ("precio_material", "ck_precio_material_moneda", ["ARS", "USD"]),
    ("pieza_cuero", "ck_pieza_cuero_moneda", ["ARS", "USD"]),
    ("tipo_cambio", "ck_tipo_cambio_tipo", ["VENDEDOR", "COMPRADOR"]),
    ("tipo_cambio", "ck_tipo_cambio_fuente", ["BNA", "EXCEL_VIEJO", "MANUAL"]),
    ("orden_fabricacion", "ck_orden_fabricacion_donde_se_hace", ["EXTERNA", "INTERNA"]),
    ("orden_fabricacion", "ck_orden_fabricacion_estado",
     ["PLANIFICADA", "EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA"]),
    ("orden_estado", "ck_orden_estado_estado",
     ["PLANIFICADA", "EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA"]),
    ("gasto_periodo", "ck_gasto_periodo_fabrica_o_tienda", ["FABRICA", "TIENDA"]),
    ("gasto_periodo", "ck_gasto_periodo_categoria",
     ["SUELDOS", "CARGAS_SOCIALES", "ALQUILER", "SERVICIOS", "IMPUESTOS_FIJOS", "OTROS"]),
    ("pieza_cuero", "ck_pieza_cuero_estado", ["ENTERA", "EN_USO", "RETAZO", "CERRADA"]),
    ("movimiento_cuero", "ck_movimiento_cuero_tipo", ["CORTE", "DESPERDICIO", "AJUSTE", "ENTRADA"]),
    ("conteo_inventario", "ck_conteo_inventario_momento", ["INICIO", "CIERRE"]),
    ("modelo_molde", "ck_modelo_molde_capa", ["EXTERIOR", "INTERIOR", "FLEX", "GOMA_EVA"]),
    ("registro_tarea", "ck_registro_tarea_tarea", ["CORTE", "CONFECCION"]),
    ("etapa", "ck_etapa_tipo", ["MATERIAL", "TAREA_INTERNA", "CONFECCION"]),
    ("cotizacion", "ck_cotizacion_tipo", ["INICIAL", "RECOTIZACION", "FINAL"]),
    ("persona", "ck_persona_rol",
     ["CONSUMO_MOLDES", "CORTE", "CONFECCION", "VENTAS", "ENCARGADO", "ADMINISTRACION", "OTRO"]),
    ("persona", "ck_persona_vinculo", ["SUELDO_FIJO", "OTRO"]),
    ("documento_proveedor", "ck_documento_proveedor_tipo", ["FACTURA", "IMAGEN", "OTRO"]),
    ("documento_proveedor", "ck_documento_proveedor_mime", ["image/jpeg", "image/png", "image/webp", "application/pdf"]),
    ("documento_proveedor", "ck_documento_proveedor_moneda", ["ARS", "USD"]),
    ("documento_proveedor", "ck_documento_proveedor_ocr_estado", ["PENDIENTE", "LISTO", "ERROR", "NO_CONFIGURADO"]),
])
def test_dropdown_lists_of_the_sheet_are_check_constraints(name, constraint, values):
    sql = check_text(name)[constraint]
    assert set(re.findall(r"'([A-Za-z_/+]+)'", sql)) == set(values)


def test_other_checks_and_unique_rules():
    assert "orden_item_id IS NOT NULL" in check_text("movimiento_cuero")["ck_movimiento_cuero_corte_requiere_orden_item"]
    assert check_text("receta_linea")["ck_receta_linea_origen"] == "origen IN ('EXTRA')"
    indexes = {i.name: str(CreateIndex(i).compile(dialect=postgresql.dialect())).lower()
               for t in Base.metadata.tables.values() for i in t.indexes}
    assert "unique" in indexes["precio_material_uq"] and "coalesce(color_id, 0)" in indexes["precio_material_uq"]
    assert "vigente_desde" in indexes["precio_material_uq"] and "material_id" in indexes["precio_material_uq"]
    assert "unique" in indexes["tipo_cambio_uq"]
    assert all(col in indexes["tipo_cambio_uq"] for col in ("fecha", "tipo", "fuente"))
    # A row can be replaced by at most one row (the correction chain never forks); NULL means "not a correction".
    assert "unique" in indexes["gasto_periodo_reemplaza_a_uq"] and "reemplaza_a_id is not null" in indexes["gasto_periodo_reemplaza_a_uq"]
    quote_unique = [tuple(c.columns.keys()) for c in table("cotizacion").constraints if isinstance(c, UniqueConstraint)]
    assert ("producto_id", "fecha", "tipo") in quote_unique


def test_calculated_columns_are_not_persisted_except_in_the_cotizacion_snapshot():
    not_persisted = {
        "producto": {"nombre", "categoria", "control", "fecha_de_cierre_usada", "lineas_extra", "para_elegir"},
        "modelo": {"codigo_del_forro", "para_elegir", "control", "productos_que_lo_usan", "orden_alfabetico"},
        "receta_linea": {"costo_hoy_ars", "precio_hoy_ars_por_unidad", "desperdicio", "unidad", "etapa"},
        "precio_material": {"es_el_vigente", "precio_ars_hoy", "clave", "control"},
        "orden_fabricacion": {"periodo", "productos", "unidades", "costo_total_del_lote_ars"},
        "orden_item": {"costo_por_unidad_ars", "total_de_la_linea_ars", "desvio_del_cuero"},
        "pieza_cuero": {"m2_que_quedan", "dolar_de_la_compra", "precio_pagado_ars_por_m2"},
        "material": {"desperdicio_medido", "desperdicio_que_se_aplica", "control"},
        "taller": {"lotes", "unidades", "cobro_en_total_ars", "para_elegir"},
        "molde": {"area_m2"},
        "conteo_inventario": {"m2_segun_libro", "diferencia_m2", "diferencia_ars"},
    }
    for name, columns in not_persisted.items():
        assert columns.isdisjoint(table(name).c.keys()), name
    assert {"cuero", "forro", "flex", "goma_eva", "herrajes", "hilo_cemento", "corte", "confeccion",
            "subtotal_etapas", "componentes_kit", "iva_compras", "arreglos", "total_ars", "total_usd",
            "dolar", "tipo", "fecha", "producto_id", "estado"} <= set(table("cotizacion").c.keys())


def test_material_has_no_price_and_missing_consumption_is_nullable():
    material = table("material")
    assert not {"precio", "moneda", "proveedor"} & set(material.c.keys())
    assert table("modelo").c.cuero_m2_por_unidad.nullable
    assert table("precio_material").c.moneda.nullable is False


def test_postgresql_ddl_compiles_for_every_table():
    dialect = postgresql.dialect()
    for t in Base.metadata.sorted_tables:
        ddl = str(CreateTable(t).compile(dialect=dialect))
        assert f"CREATE TABLE costos.{t.name}" in ddl


def test_gasto_periodo_reemplaza_a_id_is_a_nullable_self_reference():
    column = table("gasto_periodo").c.reemplaza_a_id
    assert column.nullable and str(column.type.compile(dialect=postgresql.dialect())) == "BIGINT"
    assert {fk.target_fullname for fk in column.foreign_keys} == {"costos.gasto_periodo.id"}


def test_proveedor_is_a_business_key_table_with_unique_cuit_and_a_case_insensitive_unique_name():
    t = table("proveedor")
    assert set(t.c.keys()) == {"id", "created_at", "codigo", "nombre", "cuit", "contacto", "telefono", "direccion",
                               "nota", "activo"}
    assert t.c.nombre.nullable is False and t.c.cuit.nullable is True and t.c.activo.nullable is False
    assert t.c.activo.server_default is not None
    unique = [tuple(c.columns.keys()) for c in t.constraints if isinstance(c, UniqueConstraint)]
    assert ("cuit",) in unique and ("nombre",) not in unique  # the name is unique through lower(nombre)
    index = next(i for i in t.indexes if i.name == "proveedor_nombre_uq")
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect())).lower()
    assert "unique" in ddl and "lower(nombre)" in ddl


def test_documento_proveedor_shape_defers_the_bytes_and_keeps_money_as_numeric():
    t = table("documento_proveedor")
    assert set(t.c.keys()) == {
        "id", "created_at", "proveedor_id", "tipo", "nombre_archivo", "mime", "tamano_bytes", "sha256", "contenido",
        "numero", "fecha_documento", "total", "moneda", "ocr_estado", "ocr_texto", "ocr_sugerencia", "ocr_error",
        "subido_por"}
    dialect = postgresql.dialect()
    assert str(t.c.contenido.type.compile(dialect=dialect)) == "BYTEA" and t.c.contenido.nullable is False
    assert str(t.c.ocr_sugerencia.type.compile(dialect=dialect)) == "JSONB" and t.c.ocr_sugerencia.nullable
    assert (t.c.total.type.precision, t.c.total.type.scale) == (14, 4) and t.c.total.nullable
    assert str(t.c.fecha_documento.type.compile(dialect=dialect)) == "DATE" and t.c.fecha_documento.nullable
    for nullable in ("numero", "moneda", "ocr_texto", "ocr_error", "ocr_sugerencia"):
        assert t.c[nullable].nullable, nullable
    for required in ("proveedor_id", "tipo", "nombre_archivo", "mime", "tamano_bytes", "sha256", "contenido",
                     "ocr_estado", "subido_por"):
        assert not t.c[required].nullable, required
    assert {fk.target_fullname for fk in t.foreign_keys} == {"costos.proveedor.id"}
    unique = [tuple(c.columns.keys()) for c in t.constraints if isinstance(c, UniqueConstraint)]
    assert ("proveedor_id", "sha256") in unique
    assert "contenido" in DocumentoProveedor.__mapper__.column_attrs  # mapped, but...
    assert DocumentoProveedor.__mapper__.column_attrs["contenido"].deferred is True  # ...never loaded in a list
    assert "total >= 0" in check_text("documento_proveedor")["ck_documento_proveedor_total_no_negativo"]
