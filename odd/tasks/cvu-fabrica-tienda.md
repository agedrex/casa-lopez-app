# CVU de la fábrica y de la tienda + gasto del negocio

Objective: two cost-volume-profit models (FABRICA and TIENDA) plus a view of how much the business spends (fixed costs by ámbito, categoría, month). Branch: feat/cvu-fabrica-tienda. Delivery: ask-on-risk. Test runner: `uv run --directory backend pytest -q`; front `corepack pnpm lint && corepack pnpm build`.

## Specs

- S1 "se tomen en cuenta los costos fijos del negocio también y que, de alguna forma, lleve cuánto se está gastando el negocio": resumen de costos fijos por ámbito (FABRICA/TIENDA) y categoría, del mes.
- S2 "la tienda se lo compra del costo, un 20 o 30%": precio de transferencia = costo de fábrica de hoy con margen `MARGEN_TRANSFERENCIA_PCT` (parámetro editable, "Propuesta, a confirmar"). SUPUESTO: el margen es sobre el precio de transferencia (misma convención que `precio_con_margen`); validar con Robert.
- S3 CVU de la FÁBRICA: vende a la tienda al precio de transferencia; variable = costo de fábrica; fijos = FABRICA del mes. Sin IIBB ni gastos de venta (venta interna).
- S4 CVU de la TIENDA: productos propios cuestan el precio de transferencia y se venden al precio de venta guardado; Mercadería (MER-) cuesta su último costo de compra y se vende a su precio; fijos = TIENDA del mes; con IIBB y gastos de venta.
- S5 Todo lo calcula el backend (Decimal); el volumen es un escenario tipeado (no hay tabla de ventas).
- S6 Pantalla "Negocio" con Fábrica / Tienda / Gastos; app lista para cargar productos nuevos.

## Tasks

- [ ] T1 (S2) parámetro + migración 0021 + `precio_de_transferencia`
- [ ] T2 (S1) resumen de gastos fijos + endpoint
- [ ] T3 (S3, S4, S5) escenarios fábrica y tienda + endpoints
- [ ] T4 (S6) pantalla + nav
- [ ] T5 verificación completa y estado "listo para cargar"

## Log

- L1 (2026-11-15) Pedido original: "aumentemos que, en el sistema, se tomen en cuenta los costos fijos del negocio ... modelo costo-volumen-utilidad de la tienda y ... de la fábrica ... que dejes la aplicación lista para que el día de mañana ya pueda empezar a cargar nuevos productos".
- L2 (2026-11-15) "la tienda se lo compra a un 30% o 20% de margen. Ese margen podríamos definir nosotros ... y después eso la tienda lo vende a otro precio, que es igual al precio mismo que ya tenemos".
