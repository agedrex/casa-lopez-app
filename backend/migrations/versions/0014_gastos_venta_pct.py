"""Add the parameter GASTOS_VENTA_PCT: variable selling expense as a fraction of the net price.

The sales scenario (CVU) discounts it, together with IIBB, from the contribution of each unit:
contribution = net price - variable cost - price x GASTOS_VENTA_PCT - IIBB. It starts at 0, so no number moves until a
person loads a value. Nothing is invented: the row is a placeholder marked as not confirmed.

Downgrade deletes only that row (the value a person typed in it is lost; nothing references `parametro`).
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_gastos_venta_pct"
down_revision = "0013_impuestos_vacios"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text(
        "INSERT INTO costos.parametro (codigo, constante, valor, valor_texto, unidad, que_es, fuente_estado) VALUES ("
        "'GASTOS_VENTA_PCT', 'Gastos variables de venta', 0, NULL, '%', "
        "'Parte del precio de venta sin impuestos que se va en gastos que crecen con cada venta (comisiones, envío, "
        "comisión de cobro). Se descuenta del margen de contribución del escenario. 0.05 = 5 %.', "
        "'Propuesta, a confirmar con Robert') "
        "ON CONFLICT (codigo) DO NOTHING"))


def downgrade():
    op.execute(sa.text("DELETE FROM costos.parametro WHERE codigo = 'GASTOS_VENTA_PCT'"))
