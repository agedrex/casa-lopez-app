"""Start the tax grid empty: remove the three taxes seeded from the plantilla.

The grid at /admin/impuestos is now filled by a person. The seeded IVA (21 %, COMPRA), IIBB and GANANCIAS
(no percentage) are removed so no tax applies to a sale price until someone creates one. Nothing else
references `impuesto` (the costing engine reads the IVA row only when it exists and counts a missing one as 0 %).
Only the three seeded codes are deleted; a tax created from the grid (IMP-NNNN) is left alone.

Downgrade puts the three seeded rows back (as they were in revision 0004, active).
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_impuestos_vacios"
down_revision = "0012_impuesto_activo"
branch_labels = None
depends_on = None

SEEDED_CODES = ("IVA", "IIBB", "GANANCIAS")


def upgrade():
    op.execute(sa.text("DELETE FROM costos.impuesto WHERE codigo IN ('IVA', 'IIBB', 'GANANCIAS')"))


def downgrade():
    op.execute(sa.text(
        "INSERT INTO costos.impuesto (codigo, nombre, alicuota, base, es_costo_del_producto) VALUES "
        "('IVA', 'IVA de compras', 0.21, 'COMPRA', false), "
        "('IIBB', 'Ingresos brutos', NULL, 'VENTA', false), "
        "('GANANCIAS', 'Ganancias', NULL, 'RESULTADO', false) "
        "ON CONFLICT (codigo) DO NOTHING"))
