"""Add the parameter MARGEN_TRANSFERENCIA_PCT: the margin the factory earns selling to the store.

The store pays the factory cost / (1 - margin) for the products the factory makes; the factory CVU sells at that price
and the store CVU buys at it. 0.20 = 20 % of the transfer price. It starts at 0.20 as a proposal marked as not confirmed.

Downgrade deletes only that row (the value a person typed in it is lost; nothing references `parametro`).
"""

from alembic import op
import sqlalchemy as sa

revision = "0021_margen_transferencia"
down_revision = "0020_proveedor_producto"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text(
        "INSERT INTO costos.parametro (codigo, constante, valor, valor_texto, unidad, que_es, fuente_estado) VALUES ("
        "'MARGEN_TRANSFERENCIA_PCT', 'Margen de la fábrica sobre la tienda', 0.20, NULL, '%', "
        "'Margen que gana la fábrica al venderle a la tienda: la tienda paga el costo de fábrica dividido por (1 menos "
        "este margen), sobre el precio de transferencia. 0.20 = 20 %. Lo usan el CVU de la fábrica y el de la tienda.', "
        "'Propuesta, a confirmar con Robert') "
        "ON CONFLICT (codigo) DO NOTHING"))


def downgrade():
    op.execute(sa.text("DELETE FROM costos.parametro WHERE codigo = 'MARGEN_TRANSFERENCIA_PCT'"))
