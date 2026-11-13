"""Re-insert the seeded `modelo` rows that are missing from STAGING (after recortar_staging.py trimmed them).

Only inside the staging container (`railway ssh -e staging -s backend`). Dry-run by default; writing needs `--confirmar`.
It only INSERTS the models of migrations/seed_data/seed_v3.json whose `codigo` does not exist yet (same values and
foreign keys as migration 0004): nothing is updated or deleted. Refuses any environment that is not exactly `staging`.

    python scripts/restaurar_modelos_staging.py            # dry-run
    python scripts/restaurar_modelos_staging.py --confirmar
"""

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

from backend.database import create_database_engine

SEED_FILE = Path(__file__).resolve().parents[1] / "migrations" / "seed_data" / "seed_v3.json"
SQL_TYPES = {"text": sa.Text(), "int": sa.Integer(), "bool": sa.Boolean(), "date": sa.Date(),
             "decimal": sa.Numeric(asdecimal=True), "fk": sa.BigInteger()}
CONVERTERS = {"decimal": Decimal, "date": date.fromisoformat}


def faltantes(seed: dict, existentes: set[str]) -> list[list]:
    """The seed rows (as value lists) of the model table whose codigo is not in `existentes`."""
    indice = [spec["name"] for spec in seed["columns"]].index("codigo")
    return [values for values in seed["rows"] if values[indice] not in existentes]


def fila(seed: dict, values: list) -> dict:
    row = {}
    for spec, value in zip(seed["columns"], values):
        if value is None:
            row[spec["name"]] = None
        elif spec["tag"] == "fk":
            tabla, columna = spec["ref"]
            destino = sa.table(tabla, sa.column("id"), sa.column(columna), schema="costos")
            row[spec["name"]] = sa.select(destino.c.id).where(destino.c[columna] == value).scalar_subquery()
        else:
            row[spec["name"]] = CONVERTERS.get(spec["tag"], lambda raw: raw)(value)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirmar", action="store_true", help="write (default: dry-run)")
    args = parser.parse_args(argv)
    if os.environ.get("RAILWAY_ENVIRONMENT_NAME") != "staging":
        print("Solo corre dentro del contenedor de staging (RAILWAY_ENVIRONMENT_NAME=staging).", file=sys.stderr)
        return 2
    seed = next(t for t in json.loads(SEED_FILE.read_text(encoding="utf-8"))["tables"] if t["name"] == "modelo")
    tabla = sa.table(seed["name"], *[sa.column(s["name"], SQL_TYPES[s["tag"]]) for s in seed["columns"]], schema="costos")
    engine = create_database_engine()
    with engine.begin() as conexion:
        existentes = set(conexion.execute(sa.select(tabla.c.codigo)).scalars())
        faltan = faltantes(seed, existentes)
        print(f"Modelos del seed: {len(seed['rows'])}. Ya existen: {len(existentes)}. Se insertarían: {len(faltan)}.")
        if not args.confirmar:
            print("Dry-run: no se escribió nada (agregar --confirmar).")
            return 0
        for values in faltan:
            conexion.execute(tabla.insert().values(**fila(seed, values)))
        print(f"Insertados: {len(faltan)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
