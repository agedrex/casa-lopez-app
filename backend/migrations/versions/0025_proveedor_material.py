"""Add proveedor_material: the materials of the grid that each supplier really provides.

One row per supplier + material (unique pair). Taking a material off a supplier's list sets `activo = false`; nothing is
deleted. The order form of a supplier offers only its active materials. The cost engine never reads it.

Downgrade drops the table: every supplier's list of provided materials is lost (no price and no order is touched).
"""

from alembic import op
import sqlalchemy as sa

revision = "0025_proveedor_material"
down_revision = "0024_modelo_foto"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proveedor_material',
        sa.Column('proveedor_id', sa.BigInteger(), nullable=False),
        sa.Column('material_id', sa.BigInteger(), nullable=False),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('creado_por', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proveedor_id'], ['costos.proveedor.id'], name=op.f('fk_proveedor_material_proveedor_id_proveedor')),
        sa.ForeignKeyConstraint(['material_id'], ['costos.material.id'], name=op.f('fk_proveedor_material_material_id_material')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_proveedor_material')),
        sa.UniqueConstraint('proveedor_id', 'material_id', name=op.f('uq_proveedor_material_proveedor_id_material_id')),
        schema='costos',
    )
    op.create_index(op.f('ix_proveedor_material_proveedor_id'), 'proveedor_material', ['proveedor_id'], unique=False, schema='costos')
    op.create_index(op.f('ix_proveedor_material_material_id'), 'proveedor_material', ['material_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_proveedor_material_material_id'), table_name='proveedor_material', schema='costos')
    op.drop_index(op.f('ix_proveedor_material_proveedor_id'), table_name='proveedor_material', schema='costos')
    op.drop_table('proveedor_material', schema='costos')
