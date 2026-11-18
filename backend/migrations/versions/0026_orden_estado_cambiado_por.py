"""Add orden_estado.cambiado_por: the auth user id (text, no FK) of whoever changed the state of a lot.

`orden_estado.quien_id` points to a `persona` (who in the shop did the work, picked by the admin). The taller logs in as an auth
user, which is not a persona, so the logged-in user is kept apart. Better Auth lives in `public`: no foreign key, like
`producto.creado_por`. Nullable: the creation row and the rows that already exist stay NULL and are not backfilled.

Downgrade drops the column: who changed each state is lost (the history rows stay).
"""

from alembic import op
import sqlalchemy as sa

revision = "0026_orden_estado_cambiado_por"
down_revision = "0025_proveedor_material"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orden_estado', sa.Column('cambiado_por', sa.Text(), nullable=True), schema='costos')


def downgrade():
    op.drop_column('orden_estado', 'cambiado_por', schema='costos')
