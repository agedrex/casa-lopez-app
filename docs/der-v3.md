# DER v3

Source of truth: sheet `Diccionario` of `Plantilla Costos Casa Lopez v4.1 (trabajo).xlsx`.
It supersedes [`der.md`](der.md) (DER v1) and the old Excel rules (GG 11 % is gone; CORTE is fixed; CONFECCION and HILO_CEMENTO are separate stages).
The models are in `backend/src/backend/models.py`; Alembic revision `0003_der_v3` drops the v1 tables and creates these ones, and `0004_semillas_v3` loads the reference data `0005_gasto_reemplaza_a` adds `gasto_periodo.reemplaza_a_id` `0009_gasto_anulado` adds `gasto_periodo.anulado` `0010_compra_sin_unidades` makes `compra_reventa.unidades` nullable and `0012_impuesto_activo` adds `impuesto.activo` and `0013_impuestos_vacios` removes the three seeded taxes (the tax grid starts empty) and `0014_gastos_venta_pct` adds the parameter `GASTOS_VENTA_PCT` and `0015_precio_venta_margen` adds `precio_venta.margen` and `0016_formulario_consumo` adds `formulario_consumo` and `formulario_consumo_linea` and `0017_formulario_modelo` adds `formulario_consumo.modelo_id` (the sheet measures a model; the product is created after it is validated) and `0018_pedidos_proveedor` adds `pedido_proveedor` and `pedido_linea` and the unit `m` (metre) to the closed unit lists and `0019_modelo_insumo` adds `modelo_insumo` and `0020_proveedor_producto` adds `proveedor_producto`.

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
| `impuesto` | Impuestos | Taxes with rate, base, whether they are a product cost and `activo` (revision 0012): see the section on taxes on the sale price. |
| `parametro` | Parametros | Constants by technical code (`valor` numeric or `valor_texto`), each with its `fuente_estado`. |
| `material` | Materiales | Everything that is bought: stage, consumption unit, `cotizable`, inventory control, manual waste. |
| `molde` | Moldes | Pattern pieces with measures. |
| `modelo` | Modelos | Product model with per-unit consumptions (leather, lining, flex, EVA rubber, hardware USD, thread and cement), estimated sewing cost and old-Excel reference values. |
| `modelo_molde` | Modelo_Molde | Which molds a model uses, by layer (EXTERIOR, INTERIOR, FLEX, GOMA_EVA). |
| `producto` | Productos | A model in a leather and color, who makes it, lifecycle state and the three dates (alta, recotización, cierre). |
| `receta_linea` | Receta_Extra | Only the `EXTRA` recipe lines (second leather, specific hardware); the `MODELO` lines are calculated. |
| `kit_componente` | Kits | Products inside a kit product, with quantity. |
| `precio_material` | Precios | Append-only price of a material (and optionally a color) from a date; unique per material + color + `vigente_desde`. `proveedor` is the supplier as typed (text); `proveedor_id` (nullable FK to `proveedor`, revision 0011) is the real link: see the note below. |
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
| `formulario_consumo` | (no sheet) | The digital "consumos y herrajes" sheet of one new article (revision 0016): see the section below. |
| `formulario_consumo_linea` | (no sheet) | The rows of that sheet. |
| `pedido_proveedor` | (no sheet) | A delivery from a supplier (revision 0018): see the section below. |
| `pedido_linea` | (no sheet) | The materials of that delivery and the price each one created. |
| `modelo_insumo` | (no sheet) | The supplies a model carries per unit (revision 0019): see the section below. |
| `proveedor_producto` | (no sheet) | What a supplier sells: unit, quantity and reference price (revision 0020): see the section below. |

## Resale products, shown as "Mercadería" in the app (revision 0008)

Two tables for products Casa López buys ready-made and resells. They are outside the costing engine: no materials, stages or quotes.

| Table | What it holds |
|---|---|
| `producto_reventa` | The product: `codigo` (`MER-nnnn`), name (unique ignoring case), optional `categoria_id`, free-text `proveedor`, `activo`. Archiving is `activo = false`. |
| `compra_reventa` | One row of history: date, `unidades` (> 0, or NULL for a price update typed in the Mercadería grid, revision 0010), `costo_unitario_ars` (> 0) and an optional `precio_venta_unitario_ars` (> 0). Only appended. |

The cost of a product is the unit cost of its **latest** purchase (latest `fecha`, then latest id); the sale price is the one typed in the latest purchase that has one; the cost of a purchase is `unidades × costo_unitario_ars`. The margin is computed in `backend/reventa.py` (profit over the sale price), never by the front. Admin only (read and write). SUPUESTO: validar con Casa López: ARS only (no dollar conversion), no stock (units sold are not tracked, there are no sales yet), and the `MER-` prefix is ours.

## Supplier price history (revision 0011)

`precio_material.proveedor_id` (nullable FK to `proveedor`, indexed) says which supplier a price came from. The text column `proveedor` is not touched: it keeps what was typed (`PRV-NNNN` codes from the old external file or free text). Rows are still only added; a new price of a supplier is a new row with its date.

- **Set when:** a price is loaded from the supplier's page (`POST /proveedores/{codigo}/precios`), or through `POST /precios` with a `proveedor` text that is exactly the code of an existing supplier (codes are unique).
- **Backfill (migration):** only rows whose text equals the code of a supplier that already exists. Free-text names are not matched (the same name can be written many ways); those rows stay NULL and can be linked by loading a new price from the supplier's page.
- **Reading:** a supplier's history (`GET /proveedores/{codigo}/materiales`) includes the rows linked to it and the unlinked rows whose text is its code, so a supplier created after the migration still finds its old prices (the seeded `PRV-0001` and `PRV-0002`).
- **Limit kept on purpose:** `precio_material_uq` is still one price per material + color + date. Two suppliers cannot hold a price of the same material and color on the same date, because the costing engine uses one price per material and color. A price loaded for a supplier is, like any price, the one the costs use from its date on.
- **Downgrade** drops the column and its index: the links made from the supplier's page are lost (the prices and the text stay).

The payments to a workshop need no new table: `GET /talleres/{codigo}/historial` reads the existing `orden_fabricacion` and `orden_item` (units and the paid price per unit of each line). A price counts as paid only when it is above 0.

## Taxes on the sale price (revision 0012)

`impuesto.activo` (boolean, NOT NULL, default `true`) switches a tax on or off; every existing row stays active. Nothing is deleted. The grid at `/admin/impuestos` creates taxes (`POST /impuestos`: name + percentage, code `IMP-NNNN` assigned by the API, `base` VENTA, never a product cost), edits the percentage in place (`POST /impuestos/{codigo}/alicuota`, logged with who, old and new value, like a parameter) and activates or deactivates (`POST /impuestos/{codigo}/activo`). Admin only. The percentage is a fraction `NUMERIC(6,3)` (0.21 = 21 %).

- **Taxes go on the sale price, never on the cost.** `GET /productos/{codigo}/precio-venta` and the `POST` that saves a price keep their fields and add `impuestos` (one line per active tax with a percentage: `codigo`, `nombre`, `alicuota`, `monto`), `total_impuestos` and `precio_final`. They are computed on read with `Decimal`, with the taxes active today; nothing is stored with the price.
- **The costing engine does not change**, and neither do the cost or the saved quotes. The engine only reads the `IVA` row (percentage and `es_costo_del_producto`, which is not editable and is `false`); it does not read `activo`.
- **Revision 0013** deletes the seeded IVA, IIBB and GANANCIAS (no other table references `impuesto`; the engine counts a missing IVA row as 0 %). Its downgrade puts the three back.
- **Downgrade of 0012** drops `impuesto.activo`: the deactivated taxes would be active again.
- SUPUESTO: validar con el contador: each tax is `precio × alicuota` over the net price (they do not compound), amounts rounded to 4 decimals, and the real margin stays on the price without taxes. The seeded `IVA` (21 %, `base` COMPRA in the sheet) now also applies to the sale price; `IIBB` and `GANANCIAS` have no percentage, so they add nothing until one is loaded.

## Contribution in the sales scenario (CVU multiproducto, revision 0014)

`POST /cvu/escenario` (admin only, reads and saves nothing) follows the guide "Guia CVU multiproducto": **contribution per unit = net price - variable cost - variable selling expense - IIBB per unit**. There is no `venta` table: the volume is still the one typed in the scenario, never real sales.

- **Revision 0014** inserts one `parametro` row: `GASTOS_VENTA_PCT` (fraction of the net price, `0` = nothing, `fuente_estado` "Propuesta, a confirmar con Robert"). It changes no table or column. Its downgrade deletes only that row (a value a person typed in it is lost; nothing references `parametro`).
- **Selling expense per unit** = `precio_neto × GASTOS_VENTA_PCT`. A missing or empty parameter counts 0.
- **IIBB per unit** = `precio_neto × alicuota` of the **active** tax with `base = 'VENTA'` and a percentage whose `codigo` is `IIBB` or whose name is "Ingresos brutos" / starts with "IIBB" (filtered in the scenario code; `_impuestos_activos`, the price breakdown, is unchanged). No such row, an inactive one or an empty `alicuota` counts 0 and the scenario adds the notice `IIBB_SIN_ALICUOTA` ("el margen no incluye Ingresos Brutos"). The notice does not make the scenario "no confiable" (that flag is only about fixed costs). Revision 0013 removed the seeded `IIBB` row and the tax grid assigns `IMP-NNNN` codes, so it is matched by name too: the notice shows until such a tax with a percentage exists. With two active IIBB taxes one is taken (they are not added).
- **Each line** adds `gasto_venta_unidad`, `iibb_unidad`, `horas_confeccion`, `margen_por_hora` and `ranking_por_hora`; the scenario adds `mejor_por_hora` (product code). The saved price is the net price (taxes go on top of it).
- **Contribution per workshop hour** = `margen_unidad / modelo.horas_de_confeccion`, only when the hours are known and above 0 (a kit has no model): otherwise `null`, nothing is invented. `ranking_por_hora` is 1 for the line that leaves the most per hour (the bottleneck view); the request order of the lines is kept.
- With no IIBB percentage and `GASTOS_VENTA_PCT` = 0 every number the scenario already returned is the same as before. `margen_de_contribucion` (also used by the single-product profitability and resale) takes `gasto_venta` and `iibb` as optional keyword arguments that default to 0.
- SUPUESTO: validar con el contador y con Robert: the base of both amounts is the net price, they are rounded to 4 decimals, and the rate and the percentage are loaded by a person.

## Open assumptions (`SUPUESTO: validar`)

- Units of consumption and price are a closed `CHECK` list (`m2`, `cm`, `juego`, `unidad`, `USD`, plus `m` since revision 0018) although the sheet shows it as open.
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

## Sale price and its margin (`precio_venta`, revision 0015)

`precio_venta` is only appended: one row is the price a person set for a product on a date (`vigente_desde`); the current one is the latest date, then the latest id.

| Column | What it holds |
|---|---|
| `producto_id`, `vigente_desde` | The product and the date the price starts. |
| `precio_ars` | The price without taxes, `NUMERIC(14,4)`, > 0. |
| `margen` | Revision 0015. The margin the person used to reach the price, a fraction of the price `NUMERIC(6,3)` (0.30 = 30 %). NULL = the price was typed by hand with no margin behind it (every row saved before 0015 is NULL). Check `margen IS NULL OR (margen >= 0 AND margen < 1)`. |
| `creado_por`, `nota`, `created_at` | Who saved it (auth user id as text), an optional note and when. |

`POST /productos/{codigo}/precio-venta` takes an optional `margen` (fraction, 0 to below 1, up to 3 decimals) and both it and `GET .../precio-venta` return it. The front sends it only when the price is the one suggested for the typed margin; editing the price by hand drops it. Downgrade of 0015 drops the check and the column: the saved margins are lost (the prices stay).

## Supplier orders (`pedido_proveedor`, `pedido_linea`, revision 0018)

What arrived from a supplier, how it came and what each presentation cost. **Append-only**: orders and lines are never edited or deleted (a correction is a new order). Saving an order creates one `precio_material` row per line through `servicios.crear_precio`, **all in one transaction**: if any line fails (unknown material, a price already loaded for that material and date) nothing is stored.

`pedido_proveedor`: `codigo` (`PED-NNNN`), `proveedor_id` (FK, required), `fecha_de_recepcion` (date, required), `remito` (text: the supplier's delivery note or invoice number), `documento_id` (FK to `documento_proveedor`, optional; it must belong to the same supplier), `nota` and `creado_por` (auth user id as text, no FK).

`pedido_linea`: `pedido_id` (FK), `orden` (from 1; unique with `pedido_id`), `material_id` (FK), `cantidad_presentaciones` (`NUMERIC(12,6)`, `> 0`), `presentacion` (free text: CARRETE, CAJA, ROLLO, UNIDAD...), `contenido_por_presentacion` (`NUMERIC(12,6)`, `> 0`, in the consumption unit of the material), `precio_por_presentacion` (`NUMERIC(14,4)`, `>= 0`), `moneda` (`ARS` or `USD`), `iva_incluido` and `precio_material_id` (FK, required: the price this line created).

The price created is `precio_por_presentacion / contenido_por_presentacion`, rounded half up to 4 decimals (SUPUESTO: validar), in the consumption unit of the material, with `vigente_desde = fecha_de_recepcion`, `proveedor_id` = the supplier and no colour (all colours). Endpoints: `POST /proveedores/{codigo}/pedidos` (admin, 201) and `GET /proveedores/{codigo}/pedidos` (admin and gerente; SUPUESTO: validar). The `taller` role sees nothing.

**Unit `m` (metre).** Revision 0018 replaces the CHECK constraints `ck_material_unidad_de_consumo` and `ck_precio_material_unidad_del_precio` with the list that includes `m`. Its downgrade restores the old lists, so it **fails if any `material` or `precio_material` row uses `m`**, and it drops both new tables (the prices they created stay, only the link is lost).

## Supplies of a model (`modelo_insumo`, revision 0019)

What a model carries per unit besides the leather, lining, flex and EVA: zippers, buckles, lining board... `codigo` (`MIN-NNNN`), `modelo_id` and `material_id` (FKs, required; unique together), `cantidad_por_unidad` (`NUMERIC(12,6)`, `> 0`, in the consumption unit of the material). Not append-only: validating another sheet of the same (not yet validated) model updates the quantity of an existing pair.

**Costing.** The engine treats each supply as one more material line: quantity × the unit price valid at the quote date (generic price, same lookup as every material), USD × the dollar of the date, ARS untouched, in the stage of its material. No price (or no dollar) makes the quote incomplete, with the warning `Sin precio para <material> a esa fecha`. **No double count:** supplies in the HERRAJES stage replace `modelo.herrajes_usd_por_unidad`, and supplies in HILO_CEMENTO replace `modelo.hilo_y_cemento` (and the "Falta hilo y cemento" warning); a model without supplies is costed as before.

**Filling.** Only when a consumption form is validated and its model was not validated yet: every HERRAJE row with a quantity > 0, and the CONSUMO rows FRISELINA, CARTÓN FIBRA, CARTULINA and MOIRE with a quantity > 0, whose name equals (ignoring case, accents and repeated spaces) the `nombre` or `nombre_corto` of a costable material of a material stage, are saved. A name that fits two materials is not guessed. The rows with a quantity that matched nothing are not saved and come back in `sin_material` (a list of names) in the answer of `POST /formularios/{codigo}/validar` (null in every other answer). SUPUESTO: validar; the name match is our convention. There is no manual editing yet. `GET /modelos/{codigo}` lists `insumos` (`codigo`, `material`, `nombre`, `etapa`, `unidad_de_consumo`, `cantidad_por_unidad`, `precio_unitario` and `moneda` of the generic price in force today, null when there is none). Downgrade of 0019 drops the table: the saved supplies are lost and those models change cost.

## Products a supplier sells (`proveedor_producto`, revision 0020)

The list of what each supplier sells, as the supplier's page shows it ("Productos que vende"). **Append-only**: a row is never edited or deleted. A product is identified by (supplier, `nombre` ignoring case and repeated spaces); a change of price, unit or quantity is a new row of the same product and the newest row (`vigente_desde`, then `id`) is the current one. Two changes on the same day are allowed: the later one wins.

Columns: `codigo` (`PPR-NNNN`), `proveedor_id` (FK, required), `material_id` (FK, optional: NULL while the product is not in the material list), `nombre` (required), `unidad` (the closed list `m2`, `cm`, `juego`, `unidad`, `USD`, `m`: the same `UNITS` constant and CHECK shape as `material`), `cantidad` (`NUMERIC(12,6)`, `> 0`, optional: what one presentation holds, in `unidad`), `precio_referencial` (`NUMERIC(14,4)`, `> 0`: the price of one presentation, or of one `unidad` without `cantidad`), `moneda` (`ARS` or `USD`), `iva_incluido` (default false), `vigente_desde` (date, default today, never in the future), `nota`, `creado_por` (auth user id as text, no FK).

It is a **reference, not a cost**: it creates no `precio_material` row and the engine never reads it. The API calculates `precio_por_unidad` = `precio_referencial / cantidad` (4 decimals, half up; the price itself without `cantidad`); the frontend calculates nothing. Endpoints, both admin only (the gerente has no access to suppliers): `GET /proveedores/{codigo}/productos` (the current row of each product by name, with `cargas` = rows of the product and `precio_anterior`; `?historial=true` lists every row, newest first) and `POST /proveedores/{codigo}/productos` (body `{"productos": [...]}`, 201, all or nothing, answers the current list). SUPUESTO: validar that the price is the one of the presentation and that `unidad` does not have to equal the unit of the linked material. Downgrade of 0020 drops the table: every supplier's product list with its price history is lost.

## Consumption form of a new article (`formulario_consumo`, `formulario_consumo_linea`, revision 0016)

The digital version of the paper sheet "consumos y herrajes": one form per article, filled in by the workshop and validated by the admin. It **does not cost or calculate anything** (no totals, no USD) and does not touch `modelo` or `receta_linea`. Forms are never deleted.

`formulario_consumo`:

| Column | What it holds |
|---|---|
| `codigo` | `FCO-nnnn`, the unique and immutable business key. |
| `articulo` | The article's name or code, as typed (text, required). |
| `producto_id`, `taller_id` | Optional FKs to `producto` and `taller`. SUPUESTO: validar. The sheet is per article, not per `modelo`, and the `taller` role is not tied to one workshop, so `taller_id` is informative. |
| `estado` | `BORRADOR`, `ENVIADO`, `COMPLETADO` or `VALIDADO` (check). |
| `comentario_revision` | The admin's comment when a completed form is sent back to the workshop; kept afterwards. |
| `nota` | Free text of the admin. |
| `creado_por`, `completado_por`, `validado_por` | Auth user ids as text (no FK: Better Auth lives in `public`). |
| `enviado_en`, `completado_en`, `validado_en` | `timestamptz` of each step. A return to `ENVIADO` keeps the last completion's data. |

`formulario_consumo_linea`: `formulario_id` (FK), `seccion` (`CONSUMO` or `HERRAJE`, check), `orden` (position inside the section, from 1; unique with `formulario_id` and `seccion`), `nombre` (free text, required), `cantidad` (`NUMERIC(12,6)`, NULL = not filled in, check `>= 0`: m² for a consumption, units for a hardware item) and `comentario`. The rows of a form are replaced as a whole on every save.

The preloaded rows (14 CONSUMOS and 16 HERRAJES, in the order of the paper sheet) are the constant `LINEAS_PRECARGADAS` in `backend/src/backend/formulario.py`; creating a form copies them with empty quantity and comment.

State machine: `BORRADOR` -> `ENVIADO` (admin sends) -> `COMPLETADO` (taller or admin completes) -> `VALIDADO` (admin validates), or `COMPLETADO` -> `ENVIADO` with a comment. `VALIDADO` is immutable (409); duplicating it creates a new `BORRADOR` with the same rows. A `taller` user edits only the rows, only while `ENVIADO`, and only sees `ENVIADO` and `COMPLETADO` forms. The endpoints (`/formularios...`) are documented in the module docstring of `formulario.py`. Downgrade of 0016 drops both tables: the forms and every quantity loaded are lost.

## Materials grid (`/materiales`)

The materials page is one grid grouped by stage (no separate price form). It does not change the schema: `POST /materiales/lote` (admin only, all or nothing, `backend/src/backend/materiales.py`) saves two things in one transaction.

- **Price changes** of saved materials: a changed price, currency or supplier is a **new** `precio_material` row dated today (for all colors, `color_id` NULL), written by `servicios.crear_precio`; nothing is updated. What is not sent stays as in the price in force today; a change that leaves price, currency and supplier as they are adds no row. Prices by color are never touched. A second price for the same material and day is a `409` naming the material (one price per material + color + date). A non-`cotizable` material is refused (`422`). The unit of the price is always the consumption unit of the material.
- **New materials**: `nombre`, `etapa` (only stages of type `MATERIAL`) and `unidad_de_consumo`, with an optional first price. The code is `MAT-NNNN` (SUPUESTO: validar; the seeded `MAT-CU01`... keep their sheet codes and do not count for the sequence). Names are unique ignoring case (`409`). `cotizable` is true and `controla_inventario` false; nothing else of an existing material is edited from the grid.
