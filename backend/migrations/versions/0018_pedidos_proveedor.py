"""Add pedido_proveedor and pedido_linea (what arrived from a supplier and how), and the unit 'm' (metre).

An order (`codigo` PED-NNNN) belongs to a supplier and has a reception date, an optional delivery-note text and an optional
document already uploaded for that supplier. Each line says which material arrived, how many presentations (CARRETE, CAJA,
ROLLO...), how much each one holds in the consumption unit of the material and what each costs; it also keeps the id of the
`precio_material` row it created. Orders and lines are append-only.

The closed unit list gains 'm': the CHECK constraints `ck_material_unidad_de_consumo` and `ck_precio_material_unidad_del_precio`
are replaced with the list that includes it.

Downgrade drops both tables (every order and line is lost; the prices they created stay in `precio_material`, only the
link is gone) and restores the old unit constraints. It FAILS if any `material` or `precio_material` row uses the unit 'm':
change those rows first.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_pedidos_proveedor"
down_revision = "0017_formulario_modelo"
branch_labels = None
depends_on = None

OLD_UNITS = ("m2", "cm", "juego", "unidad", "USD")
NEW_UNITS = OLD_UNITS + ("m",)
UNIT_CHECKS = (
    ("material", "unidad_de_consumo", "ck_material_unidad_de_consumo"),
    ("precio_material", "unidad_del_precio", "ck_precio_material_unidad_del_precio"),
)


def _replace_unit_checks(units):
    listed = ",".join(f"'{unit}'" for unit in units)
    for table, column, name in UNIT_CHECKS:
        op.drop_constraint(op.f(name), table, schema='costos', type_='check')
        op.create_check_constraint(op.f(name), table, f"{column} IN ({listed})", schema='costos')


def upgrade():
    _replace_unit_checks(NEW_UNITS)
    op.create_table('pedido_proveedor',
        sa.Column('proveedor_id', sa.BigInteger(), nullable=False),
        sa.Column('fecha_de_recepcion', sa.Date(), nullable=False),
        sa.Column('remito', sa.Text(), nullable=True),
        sa.Column('documento_id', sa.BigInteger(), nullable=True),
        sa.Column('nota', sa.Text(), nullable=True),
        sa.Column('creado_por', sa.Text(), nullable=False),
        sa.Column('codigo', sa.Text(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proveedor_id'], ['costos.proveedor.id'], name=op.f('fk_pedido_proveedor_proveedor_id_proveedor')),
        sa.ForeignKeyConstraint(['documento_id'], ['costos.documento_proveedor.id'], name=op.f('fk_pedido_proveedor_documento_id_documento_proveedor')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_proveedor')),
        sa.UniqueConstraint('codigo', name=op.f('uq_pedido_proveedor_codigo')),
        schema='costos',
    )
    op.create_index(op.f('ix_pedido_proveedor_proveedor_id'), 'pedido_proveedor', ['proveedor_id'], unique=False, schema='costos')
    op.create_table('pedido_linea',
        sa.Column('pedido_id', sa.BigInteger(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.BigInteger(), nullable=False),
        sa.Column('cantidad_presentaciones', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('presentacion', sa.Text(), nullable=False),
        sa.Column('contenido_por_presentacion', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('precio_por_presentacion', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('moneda', sa.CHAR(length=3), nullable=False),
        sa.Column('iva_incluido', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('precio_material_id', sa.BigInteger(), nullable=False),
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('cantidad_presentaciones > 0', name=op.f('ck_pedido_linea_cantidad_positiva')),
        sa.CheckConstraint('contenido_por_presentacion > 0', name=op.f('ck_pedido_linea_contenido_positivo')),
        sa.CheckConstraint('precio_por_presentacion >= 0', name=op.f('ck_pedido_linea_precio_no_negativo')),
        sa.CheckConstraint("moneda IN ('ARS','USD')", name=op.f('ck_pedido_linea_moneda')),
        sa.ForeignKeyConstraint(['pedido_id'], ['costos.pedido_proveedor.id'], name=op.f('fk_pedido_linea_pedido_id_pedido_proveedor')),
        sa.ForeignKeyConstraint(['material_id'], ['costos.material.id'], name=op.f('fk_pedido_linea_material_id_material')),
        sa.ForeignKeyConstraint(['precio_material_id'], ['costos.precio_material.id'], name=op.f('fk_pedido_linea_precio_material_id_precio_material')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_linea')),
        sa.UniqueConstraint('pedido_id', 'orden', name='uq_pedido_linea_pedido_id_orden'),
        schema='costos',
    )
    op.create_index(op.f('ix_pedido_linea_material_id'), 'pedido_linea', ['material_id'], unique=False, schema='costos')
    op.create_index(op.f('ix_pedido_linea_precio_material_id'), 'pedido_linea', ['precio_material_id'], unique=False, schema='costos')


def downgrade():
    op.drop_index(op.f('ix_pedido_linea_precio_material_id'), table_name='pedido_linea', schema='costos')
    op.drop_index(op.f('ix_pedido_linea_material_id'), table_name='pedido_linea', schema='costos')
    op.drop_table('pedido_linea', schema='costos')
    op.drop_index(op.f('ix_pedido_proveedor_proveedor_id'), table_name='pedido_proveedor', schema='costos')
    op.drop_table('pedido_proveedor', schema='costos')
    _replace_unit_checks(OLD_UNITS)
