"""Add producto.creado_por: the auth user id (text, no FK) of whoever created the product.

Better Auth lives in `public`, so there is no foreign key, like `cotizacion.creado_por`. The column is nullable: products that
already exist (seed, importer, demo) stay NULL and are not backfilled; the Productos list shows "—" for them.

Downgrade drops the column: who created each product is lost (the products stay).
"""

from alembic import op
import sqlalchemy as sa

revision = "0023_producto_creado_por"
down_revision = "0022_ventas_transferencias"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('producto', sa.Column('creado_por', sa.Text(), nullable=True), schema='costos')


def downgrade():
    op.drop_column('producto', 'creado_por', schema='costos')
