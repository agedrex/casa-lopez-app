"""Add precio_venta.margen: the margin the person used to reach the sale price.

It is a fraction of the sale price (0.30 = 30 %), NUMERIC(6,3) like the other percentages. NULL means the price was
typed by hand with no margin behind it; every existing row stays NULL. A check keeps it in [0, 1). Rows are still only
appended: the margin is saved with the price, never edited afterwards.

Downgrade drops the check and the column, so every saved margin is lost (the prices stay): back it up first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_precio_venta_margen"
down_revision = "0014_gastos_venta_pct"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('precio_venta', sa.Column('margen', sa.Numeric(precision=6, scale=3), nullable=True), schema='costos')
    op.create_check_constraint(
        op.f('ck_precio_venta_margen_en_rango'), 'precio_venta', 'margen IS NULL OR (margen >= 0 AND margen < 1)',
        schema='costos',
    )


def downgrade():
    op.drop_constraint(op.f('ck_precio_venta_margen_en_rango'), 'precio_venta', schema='costos', type_='check')
    op.drop_column('precio_venta', 'margen', schema='costos')
