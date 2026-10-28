"""Read-only inspection and rollback-scoped PostgreSQL constraint probes (DER v3)."""

from datetime import date
from collections import Counter
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Connection, inspect, insert, select, text
from sqlalchemy.exc import IntegrityError

from backend.models import (
    Base, Categoria, Cotizacion, Etapa, GastoPeriodo, Material, MovimientoCuero, OrdenFabricacion,
    Persona, PiezaCuero, PrecioMaterial, Producto, RecetaLinea, TipoCambio,
)


DOMAIN_TABLES = frozenset(table.name for table in Base.metadata.tables.values())
# Rows loaded by revision 0004_semillas_v3 from the plantilla (color has no names filled in yet).
SEED_COUNTS = {
    "etapa": 8, "categoria": 16, "color": 0, "material": 13, "persona": 7, "taller": 3,
    "impuesto": 3, "parametro": 8, "tipo_cambio": 1, "precio_material": 11, "modelo": 325,
    "gasto_periodo": 15,
}
EXPECTED_SEED_CODES = {
    "etapa": ["CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION"],
    "material": ["MAT-CU01", "MAT-CU02", "MAT-CU03", "MAT-CU04", "MAT-CU05", "MAT-CU06", "MAT-FO01",
                 "MAT-FO02", "MAT-FL01", "MAT-GE01", "MAT-HE00", "MAT-HC01", "MAT-CA01"],
    "persona": ["PER-0001", "PER-0002", "PER-0003", "PER-0004", "PER-0005", "PER-0006", "PER-0007"],
}
# Lagarto and yacaré stay blocked until Gerardo defines the unit of their price.
BLOCKED_MATERIALS = frozenset({"MAT-CU03", "MAT-CU04"})

PROBE_NAMES = (
    "unique_business_key", "unique_price_per_material_color_date", "valid_currency",
    "unique_exchange_rate", "unique_quote_per_date_and_type", "cut_requires_order_item",
    "known_cycle_state", "extra_recipe_origin", "known_lot_state", "period_format",
)
PROBE_CONSTRAINTS = {
    1: "uq_categoria_codigo", 2: "precio_material_uq", 3: "ck_precio_material_moneda",
    4: "tipo_cambio_uq", 5: "uq_cotizacion_producto_fecha_tipo",
    6: "ck_movimiento_cuero_corte_requiere_orden_item", 7: "ck_producto_estado_del_ciclo",
    8: "ck_receta_linea_origen", 9: "ck_orden_fabricacion_estado", 10: "ck_gasto_periodo_periodo_aaaa_mm",
}


def inspect_database(connection: Connection) -> dict[str, object]:
    tables = sorted(inspect(connection).get_table_names(schema="costos"))
    revision = connection.execute(text("SELECT version_num FROM costos.alembic_version")).scalar_one()
    counts = {
        name: connection.execute(text(f"SELECT count(*) FROM costos.{name}")).scalar_one()
        for name in SEED_COUNTS
    }
    seeds_valid = validate_seed_rows(connection)
    return {"revision": revision, "tables": tables, "counts": counts, "seeds_valid": seeds_valid}


def seed_rows_match(codes_by_table, blocked_materials) -> bool:
    """Compare the business keys of the reference seeds, preserving duplicate multiplicity."""
    return set(codes_by_table) == set(EXPECTED_SEED_CODES) and all(
        Counter(codes_by_table[name]) == Counter(expected)
        for name, expected in EXPECTED_SEED_CODES.items()
    ) and set(blocked_materials) == BLOCKED_MATERIALS


def validate_seed_rows(connection: Connection) -> bool:
    models = {"etapa": Etapa, "material": Material, "persona": Persona}
    codes = {name: connection.execute(select(model.codigo)).scalars().all() for name, model in models.items()}
    blocked = connection.execute(select(Material.codigo).where(Material.cotizable.is_(False))).scalars().all()
    return seed_rows_match(codes, blocked)


def insert_row(connection, model, **values):
    return connection.execute(insert(model).values(**values).returning(model.id)).scalar_one()


def probe_code() -> str:
    return f"WO-PROBE-{uuid4().hex[:12]}"


def prepare_probe_data(connection: Connection) -> dict[str, int]:
    """Minimal rows the probes hang from; the caller rolls everything back."""
    material_id = connection.execute(select(Material.id).where(Material.codigo == "MAT-CU01")).scalar_one()
    product_id = insert_row(connection, Producto, codigo=probe_code())
    price_id = insert_row(connection, PrecioMaterial, **price_values(material_id, vigente_desde=date(2026, 9, 2)))
    piece_id = insert_row(connection, PiezaCuero, codigo=probe_code(), material_id=material_id,
                          m2_iniciales=Decimal("1"), estado="ENTERA")
    return {"material": material_id, "product": product_id, "price": price_id, "piece": piece_id}


def price_values(material_id, **overrides):
    values = {"codigo": probe_code(), "material_id": material_id, "precio": Decimal("1"),
              "moneda": "ARS", "unidad_del_precio": "m2", "vigente_desde": date(2026, 9, 2)}
    values.update(overrides)
    return values


def quote_values(product_id, **overrides):
    values = {"producto_id": product_id, "tipo": "INICIAL", "fecha": date(2026, 9, 1), "dolar": Decimal("1545"),
              "subtotal_etapas": Decimal("0"), "total_ars": Decimal("0"), "total_usd": Decimal("0")}
    values.update(overrides)
    return values


def expect_constraint(connection, operation, rejected, constraint_name=None):
    """Each assertion owns a SAVEPOINT, preserving the surrounding transaction."""
    savepoint = connection.begin_nested()
    try:
        operation()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        return rejected and getattr(diagnostic, "constraint_name", None) == constraint_name
    else:
        return not rejected
    finally:
        savepoint.rollback()


def run_write_probe(connection: Connection, number: int, data: dict[str, int]) -> bool:
    product_id = data["product"]
    material_id = data["material"]

    def accepts(operation):
        return expect_constraint(connection, operation, rejected=False)

    def rejects(operation):
        return expect_constraint(connection, operation, rejected=True, constraint_name=PROBE_CONSTRAINTS[number])

    def twice(model, **values):
        def operation():
            for _ in range(2):
                insert_row(connection, model, **values)
        return operation

    def movement(**overrides):
        values = {"fecha": date(2026, 9, 1), "pieza_cuero_id": data["piece"], "tipo": "AJUSTE", "m2": Decimal("-0.25")}
        values.update(overrides)
        return lambda: insert_row(connection, MovimientoCuero, **values)

    match number:
        case 1:
            return rejects(lambda: [insert_row(connection, Categoria, codigo="WO-PROBE-DUP", nombre=probe_code())
                                    for _ in range(2)])
        case 2:
            return rejects(lambda: insert_row(connection, PrecioMaterial, **price_values(material_id)))
        case 3:
            return rejects(lambda: insert_row(connection, PrecioMaterial, **price_values(
                material_id, vigente_desde=date(2026, 9, 3), moneda="EUR")))
        case 4:
            return rejects(lambda: insert_row(connection, TipoCambio, fecha=date(2026, 9, 1),
                                              ars_por_usd=Decimal("1"), fuente="EXCEL_VIEJO"))
        case 5:
            return rejects(twice(Cotizacion, **quote_values(product_id)))
        case 6:
            return rejects(movement(tipo="CORTE")) and accepts(movement())
        case 7:
            return rejects(lambda: insert_row(connection, Producto, codigo=probe_code(), estado_del_ciclo="ARCHIVADO"))
        case 8:
            return rejects(lambda: insert_row(connection, RecetaLinea, codigo=probe_code(), origen="MODELO", producto_id=product_id,
                                              material_id=material_id, consumo_neto_por_unidad=Decimal("1")))
        case 9:
            return rejects(lambda: insert_row(connection, OrdenFabricacion, codigo=probe_code(),
                                              donde_se_hace="INTERNA", estado="ENVIADA"))
        case 10:
            return rejects(lambda: insert_row(connection, GastoPeriodo, codigo=probe_code(), periodo="2026-13",
                                              concepto="WO probe", fabrica_o_tienda="FABRICA", categoria="OTROS"))
        case _:
            raise ValueError("Unknown verification probe.")


def run_write_probes(connection: Connection) -> list[tuple[str, bool]]:
    data = prepare_probe_data(connection)
    return [(name, run_write_probe(connection, number, data))
            for number, name in enumerate(PROBE_NAMES, start=1)]
