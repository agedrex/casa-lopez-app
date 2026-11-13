"""Add formulario_consumo.modelo_id: the consumption sheet belongs to the model (what is designed and measured).

A product is that model in one leather and colour, so it is created after the sheet is validated. The column is
nullable: forms made before this revision keep their product link and have no model.

Downgrade drops the column: the link between each form and its model is lost (the forms and their rows stay).
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_formulario_modelo"
down_revision = "0016_formulario_consumo"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('formulario_consumo', sa.Column('modelo_id', sa.BigInteger(), nullable=True), schema='costos')
    op.create_foreign_key(
        op.f('fk_formulario_consumo_modelo_id_modelo'), 'formulario_consumo', 'modelo', ['modelo_id'], ['id'],
        source_schema='costos', referent_schema='costos')
    op.create_index(op.f('ix_formulario_consumo_modelo_id'), 'formulario_consumo', ['modelo_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_formulario_consumo_modelo_id'), table_name='formulario_consumo', schema='costos')
    op.drop_constraint(op.f('fk_formulario_consumo_modelo_id_modelo'), 'formulario_consumo', schema='costos', type_='foreignkey')
    op.drop_column('formulario_consumo', 'modelo_id', schema='costos')
