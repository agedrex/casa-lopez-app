"""Let a fixed cost be deleted without losing it: gasto_periodo.anulado.

Deleting a row only sets the flag; the row, its amount and its history stay in the table. An annulled row stops
counting in every list, total, month copy and export (the shared `_gastos_vigentes` condition). It is the only
in-place change allowed on a saved gasto_periodo row.

Downgrade drops the column, so every annulled row would count again in the totals: back up or review them before
downgrading.
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_gasto_anulado"
down_revision = "0008_reventa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'gasto_periodo', sa.Column('anulado', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        schema='costos')


def downgrade():
    op.drop_column('gasto_periodo', 'anulado', schema='costos')
