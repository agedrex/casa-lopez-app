# DER v3

Source of truth: sheet `Diccionario` of `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx`.
It supersedes [`der.md`](der.md) (DER v1) and the old Excel rules (GG 11 % is gone; CORTE is fixed; CONFECCION and HILO_CEMENTO are separate stages).
The models are in `backend/src/backend/models.py`; Alembic revision `0003_der_v3` drops the v1 tables and creates these ones, and `0004_semillas_v3` loads the reference data `0005_gasto_reemplaza_a` adds `gasto_periodo.reemplaza_a_id` `0009_gasto_anulado` adds `gasto_periodo.anulado` and `0010_compra_sin_unidades` makes `compra_reventa.unidades` nullable.

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
| `gasto_periodo` | Costos_Fijos | Monthly fixed cost (factory or store), flagged `ficticio` while the amount is invented. `reemplaza_a_id` (nullable, self-reference) marks a correction: see the note below. `anulado` (boolean, default false) marks a deleted row: see the note below. |
| `pieza_cuero` | Pieles | Each hide bought: material, color, m², price, state. |
| `movimiento_cuero` | Movimientos_Cuero | Cuts, waste, adjustments and entries of a hide; a CORTE must point to the lot item. |
| `conteo_inventario` | Conteo_Inventario | Monthly leather count (start / close) by material and color. |
| `cotizacion` | Cotizaciones | Calculated snapshot per product, type (INICIAL / RECOTIZACION / FINAL) and date: dollar, one amount per stage, subtotal, kit components, purchase VAT, repairs, totals in ARS and USD. |

## Resale products, shown as "Mercadería" in the app (revision 0008)

Two tables for products Casa López buys ready-made and resells. They are outside the costing engine: no materials, stages or quotes.

| Table | What it holds |
|---|---|
| `producto_reventa` | The product: `codigo` (`MER-nnnn`), name (unique ignoring case), optional `categoria_id`, free-text `proveedor`, `activo`. Archiving is `activo = false`. |
| `compra_reventa` | One row of history: date, `unidades` (> 0, or NULL for a price update typed in the Mercadería grid, revision 0010), `costo_unitario_ars` (> 0) and an optional `precio_venta_unitario_ars` (> 0). Only appended. |

The cost of a product is the unit cost of its **latest** purchase (latest `fecha`, then latest id); the sale price is the one typed in the latest purchase that has one; the cost of a purchase is `unidades × costo_unitario_ars`. The margin is computed in `backend/reventa.py` (profit over the sale price), never by the front. Admin only (read and write). SUPUESTO: validar con Casa López: ARS only (no dollar conversion), no stock (units sold are not tracked, there are no sales yet), and the `MER-` prefix is ours.

## Open assumptions (`SUPUESTO: validar`)

- Units of consumption and price are a closed `CHECK` list (`m2`, `cm`, `juego`, `unidad`, `USD`) although the sheet shows it as open.
- `tipo_cambio.tipo` is nullable: the migrated Excel dollar has no type yet (pending with Gerardo).
- `impuesto.base` and `cotizacion.estado` have no dropdown in the sheet, so they are free text.
- `producto.modelo_id` and dates are nullable (a kit has no model); `estado_del_ciclo` defaults to `EN_DEFINICION`.
- Consumptions are rounded to 4 decimals on load (12 values of the plantilla had more, e.g. goma EVA of MOD-0147).
- The seeded parameters keep their sheet value and `fuente_estado`; none is confirmed. The three workshops are examples.
- Codes assigned by the API when it creates rows: `PRD-nnnn` (producto), `REX-nnnn` (receta_linea), `LOT-nnnn` (orden_fabricacion), `LIT-nnnn` (orden_item); `PRE-nnnn` and `GF-nnnn` follow the seeds; the `REX`, `LOT` and `LIT` prefixes are ours (SUPUESTO: validar).
- Kits may nest up to 5 levels; a kit component counts at its stage subtotal (plantilla `Cotizaciones!O`), so IVA and repairs apply once, on the kit.
- Parameters missing from `parametro` count as 0 %; `material.desperdicio_manual` is read as a fraction (0.2 = 20 %).

## Correcting a fixed cost (`gasto_periodo.reemplaza_a_id`, revision 0005)

A loaded amount is never edited. A correction is a **new** `gasto_periodo` row (new `GF-nnnn` code, same period, concept, category, side and person) whose `reemplaza_a_id` points to the row it replaces. The old row is kept, untouched, and stops counting: every total and list that reads `gasto_periodo` (costos fijos, panel, sheets export, quality report) only takes the *current* rows, those whose `id` is not the `reemplaza_a_id` of any other row. A partial unique index (`gasto_periodo_reemplaza_a_uq`, `WHERE reemplaza_a_id IS NOT NULL`) lets a row be replaced by at most one row, so the chain never forks; to correct again, correct the current row. Copying a month (`POST /costos-fijos/copiar`) creates plain rows with `reemplaza_a_id` NULL.

## Deleting a fixed cost (`gasto_periodo.anulado`, revision 0009)

A fixed cost is never physically deleted. `POST /costos-fijos/{codigo}/anular` (or `anulados` in `POST /costos-fijos/lote`) sets `anulado = true` on the **current** row of its chain; this flag is the only in-place change allowed on a saved `gasto_periodo` row. An annulled row keeps its amount and history but is left out of every list, total, month copy, panel figure and export, because all of them read through the shared current-rows condition (not replaced by another row **and** not annulled). A row that was already corrected or already annulled cannot be annulled (409), and an annulled row cannot be corrected or filled in. Editing the person or the note of a saved row is a correction (a new row), like any other field except the amount of a pending row. Downgrading drops the column, so annulled rows would count again.

The endpoints that read and load these tables are listed in [`backend/README.md`](../backend/README.md#costing-api-t3b).
