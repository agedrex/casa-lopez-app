"""Add modelo_insumo: the supplies a model carries per unit (zippers, buckles, lining board...).

Each row (`codigo` MIN-NNNN) says how much of one material a unit of the model uses, in the consumption unit of the
material (`cantidad_por_unidad` > 0). A model has at most one row per material. The cost engine multiplies the quantity by
the unit price valid at the quote date; the rows are filled when a consumption form is validated.

Downgrade drops the table: every supply saved for a model is lost (the costs of those models go back to the
`herrajes_usd_por_unidad` and `hilo_y_cemento` amounts of the model, so their totals change).
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_modelo_insumo"
down_revision = "0018_pedidos_proveedor"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('modelo_insumo',
        sa.Column('modelo_id', sa.BigInteger(), nullable=False),
        sa.Column('material_id', sa.BigInteger(), nullable=False),
        sa.Column('cantidad_por_unidad', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('cantidad_por_unidad > 0', name=op.f('ck_modelo_insumo_cantidad_positiva')),
        sa.ForeignKeyConstraint(['modelo_id'], ['costos.modelo.id'], name=op.f('fk_modelo_insumo_modelo_id_modelo')),
        sa.ForeignKeyConstraint(['material_id'], ['costos.material.id'], name=op.f('fk_modelo_insumo_material_id_material')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_modelo_insumo')),
        sa.UniqueConstraint('codigo', name=op.f('uq_modelo_insumo_codigo')),
        sa.UniqueConstraint('modelo_id', 'material_id', name='uq_modelo_insumo_modelo_id_material_id'),
        schema='costos',
    )
    op.create_index(op.f('ix_modelo_insumo_material_id'), 'modelo_insumo', ['material_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_modelo_insumo_material_id'), table_name='modelo_insumo', schema='costos')
    op.drop_table('modelo_insumo', schema='costos')
