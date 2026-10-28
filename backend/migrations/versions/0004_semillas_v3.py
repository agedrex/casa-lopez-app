"""Load the DER v3 reference data already filled in the plantilla v4.1.

The data comes from migrations/seed_data/seed_v3.json, generated from the xlsx by
backend/scripts/generate_seed_v3.py; this revision never reads the workbook.
Foreign keys are resolved by business key inside each INSERT, so it also renders
in offline (--sql) mode. Every parameter value stays a SUPUESTO (see its
`fuente_estado`), and the three workshops are examples (flagged in `nota`).

Downgrade deletes only the seeded rows by their business key; it fails, protected
by foreign keys, if other data already references them.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "0004_semillas_v3"
down_revision = "0003_der_v3"
branch_labels = None
depends_on = None

SEED_FILE = Path(__file__).resolve().parents[1] / "seed_data" / "seed_v3.json"
SQL_TYPES = {
    "text": sa.Text(), "int": sa.Integer(), "bool": sa.Boolean(), "date": sa.Date(),
    "decimal": sa.Numeric(asdecimal=True), "fk": sa.BigInteger(),
}
CONVERTERS = {"decimal": Decimal, "date": date.fromisoformat}
# Business key used to delete a seeded row on downgrade (default: codigo).
NATURAL_KEYS = {"tipo_cambio": ("fecha", "fuente")}


def load_tables():
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))["tables"]


def seed_table(seed):
    columns = [sa.column(spec["name"], SQL_TYPES[spec["tag"]]) for spec in seed["columns"]]
    return sa.table(seed["name"], *columns, schema="costos")


def convert(spec, value):
    return CONVERTERS.get(spec["tag"], lambda raw: raw)(value)


def resolve_row(seed, values):
    row = {}
    for spec, value in zip(seed["columns"], values):
        if value is None:
            row[spec["name"]] = None
        elif spec["tag"] == "fk":
            ref_table, ref_column = spec["ref"]
            target = sa.table(ref_table, sa.column("id"), sa.column(ref_column), schema="costos")
            row[spec["name"]] = sa.select(target.c.id).where(target.c[ref_column] == value).scalar_subquery()
        else:
            row[spec["name"]] = convert(spec, value)
    return row


def upgrade():
    for seed in load_tables():
        table = seed_table(seed)
        # One INSERT per row: foreign keys are subqueries, which executemany cannot batch.
        for values in seed["rows"]:
            op.execute(table.insert().values(**resolve_row(seed, values)))


def downgrade():
    for seed in reversed(load_tables()):
        table = seed_table(seed)
        specs = {spec["name"]: (index, spec) for index, spec in enumerate(seed["columns"])}
        keys = NATURAL_KEYS.get(seed["name"], ("codigo",))
        for values in seed["rows"]:
            conditions = [table.c[key] == convert(specs[key][1], values[specs[key][0]]) for key in keys]
            op.execute(table.delete().where(sa.and_(*conditions)))
