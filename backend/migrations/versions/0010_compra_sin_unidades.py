"""Let a resale purchase record a price change without units: compra_reventa.unidades may be NULL.

The Mercadería grid edits the unit cost and the sale price in place. Each edit is still a NEW row (nothing is updated
or deleted), but it is a price update, not a purchase: it has no units. A real purchase keeps its units. The check
`unidades > 0` stays; SQL accepts it for NULL.

Downgrade makes the column NOT NULL again and fails while any price-only row exists: delete or fill those rows first
(back up before downgrading, see docs/produccion.md).
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_compra_sin_unidades"
down_revision = "0009_gasto_anulado"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('compra_reventa', 'unidades', existing_type=sa.Numeric(12, 6), nullable=True, schema='costos')


def downgrade():
    op.alter_column('compra_reventa', 'unidades', existing_type=sa.Numeric(12, 6), nullable=False, schema='costos')
