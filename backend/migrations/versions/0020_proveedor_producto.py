"""Add proveedor_producto: the list of products a supplier sells, with unit, quantity and reference price.

Each row (`codigo` PPR-NNNN) is one dated observation of a product of a supplier: its name, the unit of measure (the same
closed list as the materials: m2, cm, juego, unidad, USD, m), the quantity of one presentation (optional, > 0), the reference
price of that presentation (> 0) with its currency and `iva_incluido`, and an optional link to a material (NULL while the
product is not in the material list). The table is append-only: a change of price, unit or quantity is a new row of the same
product (same name ignoring case) and the newest row is the current one. The cost engine never reads it.

Downgrade drops the table: every product list of every supplier, with its price history, is lost (no price of
`precio_material` and no order is touched).
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_proveedor_producto"
down_revision = "0019_modelo_insumo"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proveedor_producto',
        sa.Column('proveedor_id', sa.BigInteger(), nullable=False),
        sa.Column('material_id', sa.BigInteger(), nullable=True),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('unidad', sa.Text(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('precio_referencial', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('moneda', sa.CHAR(length=3), nullable=False),
        sa.Column('iva_incluido', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('vigente_desde', sa.Date(), nullable=False),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('cantidad IS NULL OR cantidad > 0', name=op.f('ck_proveedor_producto_cantidad_positiva')),
        sa.CheckConstraint('precio_referencial > 0', name=op.f('ck_proveedor_producto_precio_positivo')),
        sa.CheckConstraint("moneda IN ('ARS','USD')", name=op.f('ck_proveedor_producto_moneda')),
        sa.CheckConstraint("unidad IN ('m2','cm','juego','unidad','USD','m')", name=op.f('ck_proveedor_producto_unidad')),
        sa.ForeignKeyConstraint(['proveedor_id'], ['costos.proveedor.id'], name=op.f('fk_proveedor_producto_proveedor_id_proveedor')),
        sa.ForeignKeyConstraint(['material_id'], ['costos.material.id'], name=op.f('fk_proveedor_producto_material_id_material')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_proveedor_producto')),
        sa.UniqueConstraint('codigo', name=op.f('uq_proveedor_producto_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_proveedor_producto_proveedor_id'), 'proveedor_producto', ['proveedor_id'], unique=False, schema='costos')
    op.create_index(op.f('ix_proveedor_producto_material_id'), 'proveedor_producto', ['material_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_proveedor_producto_material_id'), table_name='proveedor_producto', schema='costos')
    op.drop_index(op.f('ix_proveedor_producto_proveedor_id'), table_name='proveedor_producto', schema='costos')
    op.drop_table('proveedor_producto', schema='costos')
