"""Add transferencia and venta: units sent to the store and real sales, with frozen cost snapshots.

`transferencia` (`codigo` TRF-NNNN) is one send of units of a product from the factory to the store; it freezes the factory
cost of that day, the transfer price (cost / (1 - margin)) and the margin used. `venta` (`codigo` VEN-NNNN) is one real sale,
of a product of the factory (PRD-) or of a resale product (MER-), exactly one of the two; it keeps the net price charged and
freezes what the sale cost at that moment (factory cost and transfer price for a PRD sale, the latest purchase cost for a MER
sale). Both tables are append-only: a correction is another row, nothing is edited or deleted. Stock and the real margin are
computed on read, never stored.

Downgrade drops both tables: every transfer and every sale loaded, with its frozen costs, is lost (nothing else references
them).
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_ventas_transferencias"
down_revision = "0021_margen_transferencia"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('transferencia',
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('producto_id', sa.BigInteger(), nullable=False),
        sa.Column('unidades', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('costo_fabrica_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('precio_transferencia_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('margen_transferencia_pct', sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=True),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('unidades > 0', name=op.f('ck_transferencia_unidades_positivas')),
        sa.CheckConstraint('costo_fabrica_unitario_ars >= 0', name=op.f('ck_transferencia_costo_no_negativo')),
        sa.CheckConstraint('precio_transferencia_unitario_ars >= 0', name=op.f('ck_transferencia_precio_no_negativo')),
        sa.CheckConstraint('margen_transferencia_pct >= 0 AND margen_transferencia_pct < 100', name=op.f('ck_transferencia_margen_en_rango')),
        sa.ForeignKeyConstraint(['producto_id'], ['costos.producto.id'], name=op.f('fk_transferencia_producto_id_producto')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transferencia')),
        sa.UniqueConstraint('codigo', name=op.f('uq_transferencia_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_transferencia_fecha'), 'transferencia', ['fecha'], unique=False, schema='costos')
    op.create_index(op.f('ix_transferencia_producto_id'), 'transferencia', ['producto_id'], unique=False, schema='costos')
    op.create_table('venta',
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('producto_id', sa.BigInteger(), nullable=True),
        sa.Column('producto_reventa_id', sa.BigInteger(), nullable=True),
        sa.Column('unidades', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('precio_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('canal', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('costo_fabrica_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('precio_transferencia_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('costo_compra_unitario_ars', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=True),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('(producto_id IS NULL) <> (producto_reventa_id IS NULL)', name=op.f('ck_venta_un_solo_producto')),
        sa.CheckConstraint('unidades > 0', name=op.f('ck_venta_unidades_positivas')),
        sa.CheckConstraint('precio_unitario_ars > 0', name=op.f('ck_venta_precio_positivo')),
        sa.CheckConstraint('costo_fabrica_unitario_ars IS NULL OR costo_fabrica_unitario_ars >= 0', name=op.f('ck_venta_costo_fabrica_no_negativo')),
        sa.CheckConstraint('precio_transferencia_unitario_ars IS NULL OR precio_transferencia_unitario_ars >= 0', name=op.f('ck_venta_transferencia_no_negativa')),
        sa.CheckConstraint('costo_compra_unitario_ars IS NULL OR costo_compra_unitario_ars >= 0', name=op.f('ck_venta_costo_compra_no_negativo')),
        sa.CheckConstraint(
            '(producto_id IS NOT NULL AND costo_fabrica_unitario_ars IS NOT NULL '
            'AND precio_transferencia_unitario_ars IS NOT NULL AND costo_compra_unitario_ars IS NULL) '
            'OR (producto_reventa_id IS NOT NULL AND costo_compra_unitario_ars IS NOT NULL '
            'AND costo_fabrica_unitario_ars IS NULL AND precio_transferencia_unitario_ars IS NULL)',
            name=op.f('ck_venta_congelados_segun_producto')),
        sa.ForeignKeyConstraint(['producto_id'], ['costos.producto.id'], name=op.f('fk_venta_producto_id_producto')),
        sa.ForeignKeyConstraint(['producto_reventa_id'], ['costos.producto_reventa.id'], name=op.f('fk_venta_producto_reventa_id_producto_reventa')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_venta')),
        sa.UniqueConstraint('codigo', name=op.f('uq_venta_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_venta_fecha'), 'venta', ['fecha'], unique=False, schema='costos')
    op.create_index(op.f('ix_venta_producto_id'), 'venta', ['producto_id'], unique=False, schema='costos')
    op.create_index(op.f('ix_venta_producto_reventa_id'), 'venta', ['producto_reventa_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_venta_producto_reventa_id'), table_name='venta', schema='costos')
    op.drop_index(op.f('ix_venta_producto_id'), table_name='venta', schema='costos')
    op.drop_index(op.f('ix_venta_fecha'), table_name='venta', schema='costos')
    op.drop_table('venta', schema='costos')
    op.drop_index(op.f('ix_transferencia_producto_id'), table_name='transferencia', schema='costos')
    op.drop_index(op.f('ix_transferencia_fecha'), table_name='transferencia', schema='costos')
    op.drop_table('transferencia', schema='costos')
