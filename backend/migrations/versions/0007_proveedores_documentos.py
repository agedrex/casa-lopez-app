"""Add proveedor and documento_proveedor: suppliers and their invoices / images (stored as bytea) with OCR text.

The files live in the database for now (no object storage). `precio_material.proveedor` is NOT linked to the new table.

Downgrade drops both tables, so every supplier, every stored invoice or image (the files themselves) and every OCR
text is lost: back them up first.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_proveedores_documentos"
down_revision = "0006_precio_venta"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proveedor',
        sa.Column('nombre', sa.Text(), nullable=False),
        sa.Column('cuit', sa.Text(), nullable=True),
        sa.Column('contacto', sa.Text(), nullable=True),
        sa.Column('telefono', sa.Text(), nullable=True),
        sa.Column('direccion', sa.Text(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('activo', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_proveedor')),
        sa.UniqueConstraint('codigo', name=op.f('uq_proveedor_codigo')),
        sa.UniqueConstraint('cuit', name=op.f('uq_proveedor_cuit')),
        schema='costos',
    )
    op.create_index('proveedor_nombre_uq', 'proveedor', [sa.literal_column('lower(nombre)')], unique=True, schema='costos')
    op.create_table('documento_proveedor',
        sa.Column('proveedor_id', sa.BigInteger(), nullable=False),
        sa.Column('tipo', sa.Text(), nullable=False),
        sa.Column('nombre_archivo', sa.Text(), nullable=False),
        sa.Column('mime', sa.Text(), nullable=False),
        sa.Column('tamano_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.CHAR(length=64), nullable=False),
        sa.Column('contenido', sa.LargeBinary(), nullable=False),
        sa.Column('numero', sa.Text(), nullable=True),
        sa.Column('fecha_documento', sa.Date(), nullable=True),
        sa.Column('total', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('moneda', sa.CHAR(length=3), nullable=True),
        sa.Column('ocr_estado', sa.Text(), nullable=False),
        sa.Column('ocr_texto', sa.Text(), nullable=True),
        sa.Column('ocr_sugerencia', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ocr_error', sa.Text(), nullable=True),
        sa.Column('subido_por', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("tipo IN ('FACTURA','IMAGEN','OTRO')", name=op.f('ck_documento_proveedor_tipo')),
        sa.CheckConstraint("mime IN ('image/jpeg','image/png','image/webp','application/pdf')", name=op.f('ck_documento_proveedor_mime')),
        sa.CheckConstraint("moneda IN ('ARS','USD')", name=op.f('ck_documento_proveedor_moneda')),
        sa.CheckConstraint("ocr_estado IN ('PENDIENTE','LISTO','ERROR','NO_CONFIGURADO')", name=op.f('ck_documento_proveedor_ocr_estado')),
        sa.CheckConstraint('tamano_bytes > 0', name=op.f('ck_documento_proveedor_tamano_positivo')),
        sa.CheckConstraint('total IS NULL OR total >= 0', name=op.f('ck_documento_proveedor_total_no_negativo')),
        sa.ForeignKeyConstraint(['proveedor_id'], ['costos.proveedor.id'], name=op.f('fk_documento_proveedor_proveedor_id_proveedor')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_documento_proveedor')),
        sa.UniqueConstraint('proveedor_id', 'sha256', name='uq_documento_proveedor_proveedor_id_sha256'),
        schema='costos',
    )


def downgrade():
    op.drop_table('documento_proveedor', schema='costos')
    op.drop_index('proveedor_nombre_uq', table_name='proveedor', schema='costos')
    op.drop_table('proveedor', schema='costos')
