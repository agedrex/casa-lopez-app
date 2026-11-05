"""Let a fixed cost be corrected without deleting it: gasto_periodo.reemplaza_a_id.

A correction is a NEW row that points to the row it replaces; the old row is kept
and stops counting in the totals. The partial unique index lets a row be replaced
by at most one row (the chain never forks) while many rows keep NULL.

Downgrade drops the index, the foreign key and the column. Any correction row
stays as a normal row, so after a downgrade both the old and the corrected amount
would be summed again: back up or merge them before downgrading.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_gasto_reemplaza_a"
down_revision = "0004_semillas_v3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('gasto_periodo', sa.Column('reemplaza_a_id', sa.BigInteger(), nullable=True), schema='costos')
    op.create_foreign_key(
        op.f('fk_gasto_periodo_reemplaza_a_id_gasto_periodo'), 'gasto_periodo', 'gasto_periodo',
        ['reemplaza_a_id'], ['id'], source_schema='costos', referent_schema='costos',
    )
    op.create_index(
        'gasto_periodo_reemplaza_a_uq', 'gasto_periodo', ['reemplaza_a_id'], unique=True, schema='costos',
        postgresql_where=sa.text('reemplaza_a_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index('gasto_periodo_reemplaza_a_uq', table_name='gasto_periodo', schema='costos')
    op.drop_constraint(
        op.f('fk_gasto_periodo_reemplaza_a_id_gasto_periodo'), 'gasto_periodo', schema='costos', type_='foreignkey')
    op.drop_column('gasto_periodo', 'reemplaza_a_id', schema='costos')
