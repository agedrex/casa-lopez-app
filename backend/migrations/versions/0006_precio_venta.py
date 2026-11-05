"""Add precio_venta: the sale price a person sets for a product, by date (cost-volume-profit input).

Rows are only appended; the current price is the latest `vigente_desde` (then the latest id).

Downgrade drops the table, so every stored sale price is lost: back it up first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_precio_venta"
down_revision = "0005_gasto_reemplaza_a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('precio_venta',
        sa.Column('producto_id', sa.BigInteger(), nullable=False),
        sa.Column('precio_ars', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('vigente_desde', sa.Date(), nullable=False),
        sa.Column('creado_por', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('precio_ars > 0', name=op.f('ck_precio_venta_precio_positivo')),
        sa.ForeignKeyConstraint(['producto_id'], ['costos.producto.id'], name=op.f('fk_precio_venta_producto_id_producto')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_precio_venta')),
        schema='costos',
    )
    op.create_index('precio_venta_producto_fecha', 'precio_venta', ['producto_id', 'vigente_desde'], schema='costos')


def downgrade():
    op.drop_index('precio_venta_producto_fecha', table_name='precio_venta', schema='costos')
    op.drop_table('precio_venta', schema='costos')
