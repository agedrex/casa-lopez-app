"""Trim the STAGING database to two rows of each transactional / catalog table, to make it easy to read.

Only inside the staging container (`railway ssh -e staging -s backend`). Dry-run by default: it runs every DELETE in one
transaction, prints the counts before and after, and rolls back. Writing needs `--confirmar`. Refuses any environment that is
not exactly `staging` (a missing RAILWAY_ENVIRONMENT_NAME is also refused: this script never runs locally or in production).

Kept as they are (the engine needs them to cost anything): etapa, parametro, impuesto, categoria, color, material,
precio_material, tipo_cambio. Everything else is cut to two rows, keeping what the kept rows point to.
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, text

KEEP_WHOLE = ("alembic_version", "etapa", "parametro", "impuesto", "categoria", "color", "material", "precio_material", "tipo_cambio")

# Ordered statements; each one keeps only what the rows kept before it still need. `:n` is the number of rows kept.
STEPS = [
    # Two products: first those with a saved quote, then the most used in lots.
    ("tmp_producto", """CREATE TEMP TABLE keep_producto ON COMMIT DROP AS
        SELECT p.id FROM costos.producto p
        LEFT JOIN (SELECT producto_id, count(*) n FROM costos.orden_item GROUP BY 1) u ON u.producto_id = p.id
        ORDER BY EXISTS (SELECT 1 FROM costos.cotizacion c WHERE c.producto_id = p.id) DESC, coalesce(u.n, 0) DESC, p.id LIMIT :n"""),
    # Two lots: the newest ones that contain a kept product; fill with the newest lots otherwise.
    ("tmp_lote", """CREATE TEMP TABLE keep_lote ON COMMIT DROP AS
        SELECT o.id FROM costos.orden_fabricacion o
        ORDER BY EXISTS (SELECT 1 FROM costos.orden_item i JOIN keep_producto k ON k.id = i.producto_id
                         WHERE i.orden_fabricacion_id = o.id) DESC, o.id DESC LIMIT :n"""),
    ("tmp_modelo", """CREATE TEMP TABLE keep_modelo ON COMMIT DROP AS
        SELECT id FROM (
            SELECT m.id, 0 AS orden FROM costos.modelo m WHERE m.id IN (SELECT modelo_id FROM costos.producto p JOIN keep_producto k ON k.id = p.id)
            UNION ALL SELECT m.id, 1 FROM costos.modelo m) x
        GROUP BY id ORDER BY min(orden), id LIMIT :n"""),
    ("tmp_taller", """CREATE TEMP TABLE keep_taller ON COMMIT DROP AS
        SELECT id FROM (
            SELECT t.id, 0 AS orden FROM costos.taller t WHERE t.id IN (SELECT taller_id FROM costos.orden_fabricacion o JOIN keep_lote k ON k.id = o.id)
            UNION ALL SELECT t.id, 1 FROM costos.taller t) x
        GROUP BY id ORDER BY min(orden), id LIMIT :n"""),
    ("tmp_persona", """CREATE TEMP TABLE keep_persona ON COMMIT DROP AS
        SELECT id FROM (
            SELECT p.id, 0 AS orden FROM costos.persona p WHERE p.id IN (SELECT persona_id FROM costos.orden_fabricacion o JOIN keep_lote k ON k.id = o.id)
            UNION ALL SELECT p.id, 1 FROM costos.persona p) x
        GROUP BY id ORDER BY min(orden), id LIMIT :n"""),
    ("tmp_pieza", "CREATE TEMP TABLE keep_pieza ON COMMIT DROP AS SELECT id FROM costos.pieza_cuero ORDER BY id LIMIT :n"),
    ("tmp_gasto", "CREATE TEMP TABLE keep_gasto ON COMMIT DROP AS SELECT id FROM costos.gasto_periodo WHERE reemplaza_a_id IS NULL ORDER BY (persona_id IS NULL) DESC, id DESC LIMIT :n"),
    # Children first.
    ("movimiento_cuero", """DELETE FROM costos.movimiento_cuero WHERE pieza_cuero_id NOT IN (SELECT id FROM keep_pieza)
        OR orden_item_id IN (SELECT id FROM costos.orden_item WHERE orden_fabricacion_id NOT IN (SELECT id FROM keep_lote)
                             OR producto_id NOT IN (SELECT id FROM keep_producto))
        OR registro_id NOT IN (SELECT id FROM keep_persona)"""),
    ("conteo_inventario", "DELETE FROM costos.conteo_inventario"),
    ("registro_tarea", "DELETE FROM costos.registro_tarea WHERE orden_fabricacion_id NOT IN (SELECT id FROM keep_lote) OR persona_id NOT IN (SELECT id FROM keep_persona)"),
    ("orden_estado", "DELETE FROM costos.orden_estado WHERE orden_fabricacion_id NOT IN (SELECT id FROM keep_lote)"),
    ("orden_item", "DELETE FROM costos.orden_item WHERE orden_fabricacion_id NOT IN (SELECT id FROM keep_lote) OR producto_id NOT IN (SELECT id FROM keep_producto)"),
    ("pieza_cuero", "DELETE FROM costos.pieza_cuero WHERE id NOT IN (SELECT id FROM keep_pieza)"),
    ("orden_fabricacion", "DELETE FROM costos.orden_fabricacion WHERE id NOT IN (SELECT id FROM keep_lote)"),
    ("formulario_consumo_linea", "DELETE FROM costos.formulario_consumo_linea"),
    ("formulario_consumo", "DELETE FROM costos.formulario_consumo"),
    ("modelo_insumo", "DELETE FROM costos.modelo_insumo WHERE modelo_id NOT IN (SELECT id FROM keep_modelo)"),
    ("modelo_molde", "DELETE FROM costos.modelo_molde"),
    ("kit_componente", "DELETE FROM costos.kit_componente"),
    ("receta_linea", "DELETE FROM costos.receta_linea WHERE producto_id NOT IN (SELECT id FROM keep_producto)"),
    ("precio_venta", "DELETE FROM costos.precio_venta WHERE producto_id NOT IN (SELECT id FROM keep_producto)"),
    ("cotizacion", "DELETE FROM costos.cotizacion WHERE producto_id NOT IN (SELECT id FROM keep_producto)"),
    ("producto", "DELETE FROM costos.producto WHERE id NOT IN (SELECT id FROM keep_producto)"),
    ("modelo", "DELETE FROM costos.modelo WHERE id NOT IN (SELECT id FROM keep_modelo)"),
    ("gasto_periodo", "UPDATE costos.gasto_periodo SET reemplaza_a_id = NULL WHERE reemplaza_a_id IS NOT NULL AND id NOT IN (SELECT id FROM keep_gasto)"),
    ("gasto_periodo", "DELETE FROM costos.gasto_periodo WHERE id NOT IN (SELECT id FROM keep_gasto)"),
    ("taller", "DELETE FROM costos.taller WHERE id NOT IN (SELECT id FROM keep_taller)"),
    ("persona", "DELETE FROM costos.persona WHERE id NOT IN (SELECT id FROM keep_persona)"),
]


def contar(conexion) -> dict[str, int]:
    tablas = [fila[0] for fila in conexion.execute(text(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'costos' ORDER BY 1"))]
    return {tabla: conexion.execute(text(f"SELECT count(*) FROM costos.{tabla}")).scalar_one() for tabla in tablas}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirmar", action="store_true", help="write (without it: dry-run, rolled back)")
    parser.add_argument("--n", type=int, default=2, help="rows to keep per table (default 2)")
    args = parser.parse_args(argv)
    if os.environ.get("RAILWAY_ENVIRONMENT_NAME") != "staging":
        print("Solo corre dentro del contenedor de staging (RAILWAY_ENVIRONMENT_NAME debe ser exactamente 'staging').", file=sys.stderr)
        return 2
    url = os.environ["DATABASE_URL"]
    if "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url)
    with engine.connect() as conexion:
        transaccion = conexion.begin()
        antes = contar(conexion)
        try:
            for nombre, sentencia in STEPS:
                conexion.execute(text(sentencia), {"n": args.n})
            despues = contar(conexion)
        except Exception:
            transaccion.rollback()
            raise
        for tabla in antes:
            marca = "" if antes[tabla] == despues[tabla] else "  <-- recortada"
            print(f"{tabla:28} {antes[tabla]:>5} -> {despues[tabla]:>5}{marca}")
        if args.confirmar:
            transaccion.commit()
            print("\nCONFIRMADO: cambios guardados en staging.")
        else:
            transaccion.rollback()
            print("\nDRY-RUN: no se guardó nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
