"""Add producto_reventa and compra_reventa: products bought ready-made and resold, costed by what they were bought for.

The cost of a resale product is the unit cost of its latest purchase; every purchase is a new row (the cost varies).
No materials, stages or quotes are involved.

Downgrade drops both tables, so every resale product and every purchase is lost: back them up first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_reventa"
down_revision = "0007_proveedores_documentos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('producto_reventa',
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('categoria_id', sa.BigInteger(), nullable=True),
        sa.Column('proveedor', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['categoria_id'], ['costos.categoria.id'], name=op.f('fk_producto_reventa_categoria_id_categoria')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_producto_reventa')),
        sa.UniqueConstraint('codigo', name=op.f('uq_producto_reventa_codigo')),
        schema='costos',
    )
    op.create_index('producto_reventa_nombre_uq', 'producto_reventa', [sa.literal_column('lower(nombre)')], unique=True, schema='costos')
    op.create_table('compra_reventa',
        sa.Column('producto_reventa_id', sa.BigInteger(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('unidades', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('costo_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('precio_venta_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('proveedor', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=True),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('unidades > 0', name=op.f('ck_compra_reventa_unidades_positivas')),
        sa.CheckConstraint('costo_unitario_ars > 0', name=op.f('ck_compra_reventa_costo_positivo')),
        sa.CheckConstraint('precio_venta_unitario_ars IS NULL OR precio_venta_unitario_ars > 0', name=op.f('ck_compra_reventa_precio_venta_positivo')),
        sa.ForeignKeyConstraint(['producto_reventa_id'], ['costos.producto_reventa.id'], name=op.f('fk_compra_reventa_producto_reventa_id_producto_reventa')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compra_reventa')),
        schema='costos',
    )
    op.create_index('compra_reventa_producto_fecha', 'compra_reventa', ['producto_reventa_id', 'fecha'], schema='costos')


def downgrade():
    op.drop_index('compra_reventa_producto_fecha', table_name='compra_reventa', schema='costos')
    op.drop_table('compra_reventa', schema='costos')
    op.drop_index('producto_reventa_nombre_uq', table_name='producto_reventa', schema='costos')
    op.drop_table('producto_reventa', schema='costos')
