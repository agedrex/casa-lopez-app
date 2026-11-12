"""Link a material price to its supplier: precio_material.proveedor_id (nullable FK to proveedor).

The text column `precio_material.proveedor` stays exactly as it is (it holds PRV-NNNN codes from the old external file
and free text) and nothing is deleted. Rows are only ever added: the new column just says which supplier a price came
from, so a supplier can show the history of what it charged for each material.

Backfill: a row is linked only when its text equals the code of an existing supplier (codes are unique, so the match
is unambiguous). Free-text names are NOT matched: the same name can be written in several ways. Everything else stays
NULL and can be linked by loading a new price from the supplier's page. The API also reads a row with no link as
belonging to the supplier whose code is in its text, so suppliers created after this revision still find their old prices.

Downgrade drops the column and its index: the links made from the supplier's page are lost (the text column and the
prices stay). Back up before downgrading (docs/produccion.md).
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_precio_material_proveedor"
down_revision = "0010_compra_sin_unidades"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('precio_material', sa.Column('proveedor_id', sa.BigInteger(), nullable=True), schema='costos')
    op.create_foreign_key(
        op.f('fk_precio_material_proveedor_id_proveedor'), 'precio_material', 'proveedor', ['proveedor_id'], ['id'],
        source_schema='costos', referent_schema='costos')
    op.create_index(op.f('ix_precio_material_proveedor_id'), 'precio_material', ['proveedor_id'], schema='costos')
    op.execute(
        "UPDATE costos.precio_material AS pm SET proveedor_id = p.id FROM costos.proveedor AS p "
        "WHERE pm.proveedor_id IS NULL AND pm.proveedor = p.codigo")


def downgrade():
    op.drop_index(op.f('ix_precio_material_proveedor_id'), table_name='precio_material', schema='costos')
    op.drop_constraint(
        op.f('fk_precio_material_proveedor_id_proveedor'), 'precio_material', schema='costos', type_='foreignkey')
    op.drop_column('precio_material', 'proveedor_id', schema='costos')
