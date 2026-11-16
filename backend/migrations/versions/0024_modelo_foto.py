"""Add modelo_foto: the photos of a model (stored as bytea, like `documento_proveedor`).

Each upload is a new row (`codigo` MFO-NNNN) and the newest row of a model is its current photo; nothing is updated or
deleted. The type (JPEG, PNG or WebP) is checked by its magic bytes in the service and fenced again by the CHECK below.

Downgrade drops the table: every stored photo (the image bytes themselves) is lost, the models stay. Back them up first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0024_modelo_foto"
down_revision = "0023_producto_creado_por"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('modelo_foto',
        sa.Column('modelo_id', sa.BigInteger(), nullable=False),
        sa.Column('contenido', sa.LargeBinary(), nullable=False),
        sa.Column('tipo_mime', sa.Text(), nullable=False),
        sa.Column('sha256', sa.CHAR(length=64), nullable=False),
        sa.Column('tamano_bytes', sa.Integer(), nullable=False),
        sa.Column('subido_por', sa.Text(), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("tipo_mime IN ('image/jpeg','image/png','image/webp')", name=op.f('ck_modelo_foto_tipo_mime')),
        sa.CheckConstraint('tamano_bytes > 0', name=op.f('ck_modelo_foto_tamano_positivo')),
        sa.ForeignKeyConstraint(['modelo_id'], ['costos.modelo.id'], name=op.f('fk_modelo_foto_modelo_id_modelo')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_modelo_foto')),
        sa.UniqueConstraint('codigo', name=op.f('uq_modelo_foto_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_modelo_foto_modelo_id'), 'modelo_foto', ['modelo_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_modelo_foto_modelo_id'), table_name='modelo_foto', schema='costos')
    op.drop_table('modelo_foto', schema='costos')
