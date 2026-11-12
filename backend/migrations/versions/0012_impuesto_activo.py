"""Let a tax be switched off without losing it: impuesto.activo.

Taxes are now an editable grid that applies to the sale price a person designated (precio_venta), never to the cost.
Only the active ones with a percentage show in the price breakdown. Nothing is deleted: deactivating sets the flag.
The costing engine does not read this flag (it only reads the VAT row, and only when `es_costo_del_producto` is on).
Every existing row stays active, so the seeded VAT of 21 % shows from the start.

Downgrade drops the column: the deactivated taxes would be active again, so review the grid before downgrading.
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_impuesto_activo"
down_revision = "0011_precio_material_proveedor"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'impuesto', sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False), schema='costos')


def downgrade():
    op.drop_column('impuesto', 'activo', schema='costos')
