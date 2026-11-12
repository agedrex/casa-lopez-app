"""Add formulario_consumo and formulario_consumo_linea: the digital "consumos y herrajes" sheet of a new article.

One form per article (`codigo` FCO-NNNN) with a state BORRADOR -> ENVIADO -> COMPLETADO -> VALIDADO, and its rows (a
consumption in m2 or a hardware item) with a nullable quantity. Nothing is calculated or costed in these tables. The
preloaded rows are not seeded here: the backend copies them into every new form.

Downgrade drops both tables, so every form, every row and every quantity a workshop filled in is lost: back them up first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_formulario_consumo"
down_revision = "0015_precio_venta_margen"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('formulario_consumo',
        sa.Column('articulo', sa.Text(), nullable=False),
        sa.Column('producto_id', sa.BigInteger(), nullable=True),
        sa.Column('taller_id', sa.BigInteger(), nullable=True),
        sa.Column('estado', sa.Text(), nullable=False),
        sa.Column('comentario_revision', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=False),
        sa.Column('enviado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completado_por', sa.Text(), nullable=True),
        sa.Column('completado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validado_por', sa.Text(), nullable=True),
        sa.Column('validado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("estado IN ('BORRADOR','ENVIADO','COMPLETADO','VALIDADO')", name=op.f('ck_formulario_consumo_estado')),
        sa.ForeignKeyConstraint(['producto_id'], ['costos.producto.id'], name=op.f('fk_formulario_consumo_producto_id_producto')),
        sa.ForeignKeyConstraint(['taller_id'], ['costos.taller.id'], name=op.f('fk_formulario_consumo_taller_id_taller')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_formulario_consumo')),
        sa.UniqueConstraint('codigo', name=op.f('uq_formulario_consumo_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_formulario_consumo_producto_id'), 'formulario_consumo', ['producto_id'], unique=False, schema='costos')
    op.create_table('formulario_consumo_linea',
        sa.Column('formulario_id', sa.BigInteger(), nullable=False),
        sa.Column('seccion', sa.Text(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("seccion IN ('CONSUMO','HERRAJE')", name=op.f('ck_formulario_consumo_linea_seccion')),
        sa.CheckConstraint('cantidad IS NULL OR cantidad >= 0', name=op.f('ck_formulario_consumo_linea_cantidad_no_negativa')),
        sa.ForeignKeyConstraint(['formulario_id'], ['costos.formulario_consumo.id'], name=op.f('fk_formulario_consumo_linea_formulario_id_formulario_consumo')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_formulario_consumo_linea')),
        sa.UniqueConstraint('formulario_id', 'seccion', 'orden', name='uq_formulario_consumo_linea_formulario_id_seccion_orden'),
        schema='costos',
    )


def downgrade():
    op.drop_table('formulario_consumo_linea', schema='costos')
    op.drop_index(op.f('ix_formulario_consumo_producto_id'), table_name='formulario_consumo', schema='costos')
    op.drop_table('formulario_consumo', schema='costos')
