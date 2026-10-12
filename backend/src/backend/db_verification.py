"""Read-only inspection and rollback-scoped PostgreSQL constraint probes."""

from datetime import date
from collections import Counter
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Connection, inspect, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from backend.models import (
    Base, Categoria, Cotizacion, CotizacionLinea, Etapa, MarcaCalidad,
    Material, Parametro, PrecioMaterial, Producto, Proveedor, TipoCambio,
)


DOMAIN_TABLES = frozenset(table.name for table in Base.metadata.tables.values())
SEED_COUNTS = {
    "etapa": 8, "material": 11, "proveedor": 2, "precio_material": 11,
    "tipo_cambio": 1, "parametro": 2, "categoria": 3,
}
# Exact initial VALUES and defaults from docs/der-borrador.sql; no database IDs.
EXPECTED_SEED_ROWS = {'etapa': [('CUERO', 'Cuero (capa externa)', 'material exterior', 1, True),
           ('FORRO', 'Forro (capa interna)', 'material interior', 2, True),
           ('HERRAJES', 'Herrajes, hilo y cemento', 'accesorios y detalles', 3, False),
           ('REFUERZO', 'Refuerzos (flex, goma EVA)', 'accesorios y detalles', 4, True),
           ('CORTE', 'Corte', 'refinamiento', 5, False),
           ('REB', 'Reb (supuesto: rebajado)', 'refinamiento', 6, False),
           ('PREP', 'Prep (supuesto: preparación)', 'refinamiento', 7, False),
           ('MANO_OBRA', 'Mano de obra (estimación)', 'mano de obra', 8, False)],
 'material': [('Estándar (Anilina Fina Lisa - C Arena)', 'cuero', 'm2', 'cuero:1', True, None, True),
              ('Carpincho', 'cuero', 'm2', 'cuero:2', True, None, True),
              ('Lagarto',
               'cuero',
               'm2',
               'cuero:3',
               False,
               'Precio en USD por cm (texto en G9). Bloqueado hasta definir unidad.',
               True),
              ('Yacaré overo',
               'cuero',
               'm2',
               'cuero:4',
               False,
               'Precio en USD por cm (texto en G10). Bloqueado hasta definir unidad.',
               True),
              ('Grano largo', 'cuero', 'm2', 'cuero:5', True, 'H11 tipeado 34040 (= 23 x 1480).', True),
              ('Camuflado / vaca con pelo', 'cuero', 'm2', 'cuero:6', True, None, True),
              ('Potro / Popurri / Cuero', 'forro', 'm2', 'forro:1', True, None, True),
              ('Tela forrería (Gross textil 1 x 1,50)',
               'forro',
               'm2',
               'forro:2',
               True,
               'G14 dice U$S pero es precio en pesos.',
               True),
              ('Flex 1 x 1,40 m x 0,8 mm', 'refuerzo', 'm2', 'insumo:W5', True, None, True),
              ('Goma EVA 1 x 1,40 x 2 mm', 'refuerzo', 'm2', 'insumo:W6', True, None, True),
              ('Cartón 1,5 mm', 'refuerzo', 'm2', 'insumo:W10', True, 'No lo usa ninguna fórmula.', True)],
 'proveedor': [('Rouez', 'refuerzos', None, None, None, None, None, True),
               ('Acropol', 'refuerzos', None, None, None, None, None, True)],
 'precio_material': [('cuero:1',
                      None,
                      Decimal('24'),
                      'USD',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G7'),
                     ('cuero:2',
                      None,
                      Decimal('80'),
                      'USD',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G8'),
                     ('cuero:3',
                      None,
                      Decimal('26'),
                      'USD',
                      'cm',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G9 (texto)'),
                     ('cuero:4',
                      None,
                      Decimal('3'),
                      'USD',
                      'cm',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G10 (texto)'),
                     ('cuero:5',
                      None,
                      Decimal('34040'),
                      'ARS',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!H11 (tipeado)'),
                     ('cuero:6',
                      None,
                      Decimal('35'),
                      'USD',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G12'),
                     ('forro:1',
                      None,
                      Decimal('19'),
                      'USD',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!G13'),
                     ('forro:2',
                      None,
                      Decimal('4053'),
                      'ARS',
                      'm2',
                      'rollo/plancha 1 x 1,50 m',
                      Decimal('6080'),
                      Decimal('1.50'),
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!W7 (V7 = 6080)'),
                     ('insumo:W5',
                      'Rouez',
                      Decimal('10000'),
                      'ARS',
                      'm2',
                      'rollo/plancha 1 x 1,40 m',
                      Decimal('14000'),
                      Decimal('1.40'),
                      date(2026, 9, 3),
                      'excel_migracion',
                      'Marroquineria1!W5 (V5 = 14000)'),
                     ('insumo:W6',
                      'Acropol',
                      Decimal('5857'),
                      'ARS',
                      'm2',
                      'rollo/plancha 1 x 1,40 m x 2 mm',
                      Decimal('8200'),
                      Decimal('1.40'),
                      date(2026, 9, 3),
                      'excel_migracion',
                      'Marroquineria1!W6 (V6 = 8200)'),
                     ('insumo:W10',
                      None,
                      Decimal('12250'),
                      'ARS',
                      'm2',
                      None,
                      None,
                      None,
                      date(2026, 9, 1),
                      'excel_migracion',
                      'Marroquineria1!W10')],
 'tipo_cambio': [(date(2026, 9, 1), Decimal('1545'), 'manual Excel', 'Marroquineria1!G15')],
 'parametro': [('GG_PCT',
                Decimal('11'),
                date(2026, 9, 1),
                'supuesto',
                'excel_migracion',
                'Marroquineria1!G16'),
               ('GANANCIA_PCT',
                Decimal('0'),
                date(2026, 9, 1),
                'supuesto',
                'excel_migracion',
                'Marroquineria1!G17 (no la usa ninguna fórmula)')],
 'categoria': [('Portafolio', True), ('Cartera', True), ('Billetera', True)]}

PROBE_NAMES = (
    "duplicate_model_allowed", "one_current_quote", "unique_quote_version",
    "nullable_nonnegative_quantity", "valid_currency", "quality_mark_target",
    "unique_price_without_supplier", "different_base_product", "known_parameter_key",
    "non_draft_calculated_costs", "price_requires_material", "paired_presentation",
)
PROBE_CONSTRAINTS = {
    2: "cotizacion_una_vigente", 3: "uq_cotizacion_producto_id",
    4: "ck_cotizacion_linea_cantidad_no_negativa", 5: "ck_cotizacion_linea_moneda",
    6: "ck_marca_calidad_alguna_entidad", 7: "precio_material_uq",
    8: "ck_producto_base_distinta", 9: "ck_parametro_clave",
    10: "ck_cotizacion_costos_calculados", 11: "ck_cotizacion_linea_precio_requiere_material",
    12: "ck_precio_material_presentacion_completa",
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


def seed_rows_match(rows_by_table) -> bool:
    """Compare all initial catalog contents, preserving duplicate multiplicity."""
    return set(rows_by_table) == set(EXPECTED_SEED_ROWS) and all(
        Counter(tuple(row) for row in rows_by_table[name]) == Counter(expected)
        for name, expected in EXPECTED_SEED_ROWS.items()
    )


def validate_seed_rows(connection: Connection) -> bool:
    statements = {
        "etapa": select(Etapa.codigo, Etapa.nombre, Etapa.grupo, Etapa.orden, Etapa.requiere_material),
        "material": select(Material.nombre, Material.tipo, Material.unidad_consumo, Material.codigo_excel,
                           Material.cotizable, Material.notas, Material.activo),
        "proveedor": select(Proveedor.nombre, Proveedor.categorias, Proveedor.cuit, Proveedor.direccion,
                            Proveedor.telefono, Proveedor.contacto, Proveedor.notas, Proveedor.activo),
        "precio_material": select(Material.codigo_excel, Proveedor.nombre, PrecioMaterial.precio,
            PrecioMaterial.moneda, PrecioMaterial.unidad_precio, PrecioMaterial.presentacion,
            PrecioMaterial.precio_presentacion, PrecioMaterial.contenido_presentacion,
            PrecioMaterial.vigente_desde, PrecioMaterial.fuente, PrecioMaterial.fuente_detalle
        ).select_from(PrecioMaterial).join(Material, PrecioMaterial.material_id == Material.id).outerjoin(
            Proveedor, PrecioMaterial.proveedor_id == Proveedor.id),
        "tipo_cambio": select(TipoCambio.fecha, TipoCambio.valor, TipoCambio.fuente, TipoCambio.fuente_detalle),
        "parametro": select(Parametro.clave, Parametro.valor, Parametro.vigente_desde,
                            Parametro.estado_validacion, Parametro.fuente, Parametro.fuente_detalle),
        "categoria": select(Categoria.nombre, Categoria.activo),
    }
    return seed_rows_match({name: connection.execute(statement).all() for name, statement in statements.items()})


def insert_row(connection, model, **values):
    return connection.execute(insert(model).values(**values).returning(model.id)).scalar_one()


def prepare_probe_data(connection: Connection) -> dict[str, int]:
    category_id = insert_row(connection, Categoria, nombre=f"WO 2 verification {uuid4().hex}")
    product_id = insert_row(connection, Producto, nombre="WO 2 verification", categoria_id=category_id)
    material_id = insert_row(connection, Material, nombre="WO 2 verification", tipo="cuero", unidad_consumo="m2")
    stage_id = connection.execute(select(Etapa.id).where(Etapa.codigo == "CUERO")).scalar_one()
    quote_id = insert_row(connection, Cotizacion, **quote_values(product_id))
    price_id = insert_row(connection, PrecioMaterial, **price_values(material_id))
    return {"category": category_id, "product": product_id, "material": material_id,
            "stage": stage_id, "quote": quote_id, "price": price_id}


def quote_values(product_id, **overrides):
    values = {"producto_id": product_id, "version": 1, "estado": "borrador",
              "fecha": date(2026, 9, 1), "tc_valor": Decimal("1545"),
              "gg_pct": Decimal("11"), "origen": "manual"}
    values.update(overrides)
    return values


def price_values(material_id, **overrides):
    values = {"material_id": material_id, "proveedor_id": None, "precio": Decimal("1"),
              "moneda": "ARS", "unidad_precio": "m2", "vigente_desde": date(2026, 9, 1), "fuente": "manual"}
    values.update(overrides)
    return values


def line_values(data, **overrides):
    values = {"cotizacion_id": data["quote"], "etapa_id": data["stage"],
              "concepto": "WO 2 verification", "cantidad": None, "unidad": "m2",
              "precio_unitario": Decimal("1"), "moneda": "ARS",
              "precio_unitario_ars": Decimal("1"), "total_ars": Decimal("0"), "origen_valor": "manual"}
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
    full_costs = {key: Decimal("1") for key in ("subtotal_ars", "gg_ars", "costo_ars", "costo_usd")}

    def accepts(operation):
        return expect_constraint(connection, operation, rejected=False)

    def rejects(operation):
        return expect_constraint(connection, operation, rejected=True, constraint_name=PROBE_CONSTRAINTS[number])

    def duplicate_model():
        for _ in range(2):
            insert_row(connection, Producto, nombre="WO 2 repeated model", codigo_modelo="514")

    def second_current():
        insert_row(connection, Cotizacion, **quote_values(product_id, version=2, estado="vigente", **full_costs))
        insert_row(connection, Cotizacion, **quote_values(product_id, version=3, estado="vigente", **full_costs))

    match number:
        case 1:
            return accepts(duplicate_model)
        case 2:
            return rejects(second_current)
        case 3:
            return rejects(lambda: insert_row(connection, Cotizacion, **quote_values(product_id)))
        case 4:
            return accepts(lambda: insert_row(connection, CotizacionLinea, **line_values(data))) and rejects(
                lambda: insert_row(connection, CotizacionLinea, **line_values(data, cantidad=Decimal("-1"))))
        case 5:
            return rejects(lambda: insert_row(connection, CotizacionLinea, **line_values(data, moneda="EUR")))
        case 6:
            return rejects(lambda: insert_row(connection, MarcaCalidad, tipo="WO 2 verification"))
        case 7:
            return rejects(lambda: insert_row(connection, PrecioMaterial, **price_values(data["material"])))
        case 8:
            return rejects(lambda: connection.execute(update(Producto).where(Producto.id == product_id).values(producto_base_id=product_id)))
        case 9:
            return rejects(lambda: insert_row(connection, Parametro, clave="IVA_PCT", valor=Decimal("0"),
                                           vigente_desde=date(2026, 9, 1), fuente="manual"))
        case 10:
            missing = dict(full_costs, costo_ars=None)
            return rejects(lambda: insert_row(connection, Cotizacion, **quote_values(product_id, version=2, estado="vigente", **missing))) and accepts(
                lambda: insert_row(connection, Cotizacion, **quote_values(product_id, version=2)))
        case 11:
            return rejects(lambda: insert_row(connection, CotizacionLinea, **line_values(data, precio_material_id=data["price"])))
        case 12:
            return rejects(lambda: insert_row(connection, PrecioMaterial, **price_values(data["material"],
                vigente_desde=date(2026, 9, 2), presentacion="WO 2 verification")))
        case _:
            raise ValueError("Unknown verification probe.")


def run_write_probes(connection: Connection) -> list[tuple[str, bool]]:
    data = prepare_probe_data(connection)
    return [(name, run_write_probe(connection, number, data))
            for number, name in enumerate(PROBE_NAMES, start=1)]
