# DER v3

Source of truth: sheet `Diccionario` of `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx`.
It supersedes [`der.md`](der.md) (DER v1) and the old Excel rules (GG 11 % is gone; CORTE is fixed; CONFECCION and HILO_CEMENTO are separate stages).
The models are in `backend/src/backend/models.py`; Alembic revision `0003_der_v3` drops the v1 tables and creates these ones, and `0004_semillas_v3` loads the reference data.

Only columns marked `carga` / `clave` in the dictionary are persisted. Columns marked `calculada (la app recalcula)` are computed by the backend, except in `cotizacion`, which stores a calculated snapshot. Sheets marked `vista` are not tables.

Conventions: schema `costos`; `id` (identity) and `created_at` everywhere; `codigo` is the unique, immutable business key wherever the sheet has a *Código* column; foreign keys point to ids; money `NUMERIC(14,4)`, consumptions `NUMERIC(10,4)`, dollar `NUMERIC(12,4)`, percentages `NUMERIC(6,3)`; dropdown lists of the sheet are `CHECK` constraints; nothing is deleted and prices and exchange rates are only appended with a date.

## Tables

| Table | Sheet | What it holds |
|---|---|---|
| `etapa` | Etapas | The 8 fixed stages (CUERO, FORRO, FLEX, GOMA_EVA, HERRAJES, HILO_CEMENTO, CORTE, CONFECCION) with type and treatment. |
| `categoria` | Categorias | Product categories chosen in `modelo`. |
| `color` | Colores | Colors chosen in products, prices and leather. Empty until Casa López fills the list. |
| `persona` | Personas | People with role and link (salaried or other). |
| `taller` | Talleres | External workshops (CUIT, contact). |
| `impuesto` | Impuestos | Taxes with rate, base and whether they are a product cost. |
| `parametro` | Parametros | Constants by technical code (`valor` numeric or `valor_texto`), each with its `fuente_estado`. |
| `material` | Materiales | Everything that is bought: stage, consumption unit, `cotizable`, inventory control, manual waste. |
| `molde` | Moldes | Pattern pieces with measures. |
| `modelo` | Modelos | Product model with per-unit consumptions (leather, lining, flex, EVA rubber, hardware USD, thread and cement), estimated sewing cost and old-Excel reference values. |
| `modelo_molde` | Modelo_Molde | Which molds a model uses, by layer (EXTERIOR, INTERIOR, FLEX, GOMA_EVA). |
| `producto` | Productos | A model in a leather and color, who makes it, lifecycle state and the three dates (alta, recotización, cierre). |
| `receta_linea` | Receta_Extra | Only the `EXTRA` recipe lines (second leather, specific hardware); the `MODELO` lines are calculated. |
| `kit_componente` | Kits | Products inside a kit product, with quantity. |
| `precio_material` | Precios | Append-only price of a material (and optionally a color) from a date; unique per material + color + `vigente_desde`. |
| `tipo_cambio` | Dolar | Dollar per date, type (VENDEDOR / COMPRADOR) and source; unique per date + type + source. |
| `orden_fabricacion` | Lotes | A lot sent to a workshop or made in house, with state and dates. |
| `orden_item` | Lote_Productos | A product in a lot with quantity, asked and paid workshop price per unit. |
| `orden_estado` | Lote_Estados | State history of a lot. |
| `registro_tarea` | Registro_Tareas | Cutting or sewing work by person (units, hours). |
| `gasto_periodo` | Costos_Fijos | Monthly fixed cost (factory or store), flagged `ficticio` while the amount is invented. |
| `pieza_cuero` | Pieles | Each hide bought: material, color, m², price, state. |
| `movimiento_cuero` | Movimientos_Cuero | Cuts, waste, adjustments and entries of a hide; a CORTE must point to the lot item. |
| `conteo_inventario` | Conteo_Inventario | Monthly leather count (start / close) by material and color. |
| `cotizacion` | Cotizaciones | Calculated snapshot per product, type (INICIAL / RECOTIZACION / FINAL) and date: dollar, one amount per stage, subtotal, kit components, purchase VAT, repairs, totals in ARS and USD. |

## Open assumptions (`SUPUESTO: validar`)

- Units of consumption and price are a closed `CHECK` list (`m2`, `cm`, `juego`, `unidad`, `USD`) although the sheet shows it as open.
- `tipo_cambio.tipo` is nullable: the migrated Excel dollar has no type yet (pending with Gerardo).
- `impuesto.base` and `cotizacion.estado` have no dropdown in the sheet, so they are free text.
- `producto.modelo_id` and dates are nullable (a kit has no model); `estado_del_ciclo` defaults to `EN_DEFINICION`.
- Consumptions are rounded to 4 decimals on load (12 values of the plantilla had more, e.g. goma EVA of MOD-0147).
- The seeded parameters keep their sheet value and `fuente_estado`; none is confirmed. The three workshops are examples.
