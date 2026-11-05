# CVU: rentabilidad del precio de venta

Objective: the owner types a sale price and sees if it is profitable following cost-volume-profit (contribution margin first, break-even with sales mix later).
Branch: feat/panel-cvu. Delivery: single PR for U1+U2 (ask-on-risk). Test runner: backend `.venv/bin/python -m pytest -q`.

## Specs

- S1 "Cuando ponga el precio pueda ver si le está siendo rentable o no en base al framework CVU". (L1)
- S2 The sale price is stored with a date, append-only (no UPDATE): table `precio_venta`. This reverses the earlier panel-costos S1 ("never stored"), requested in L1/L2. Money is ARS only (`precio_ars`).
- S3 Contribution margin per unit = precio - costo variable por unidad. MC % = MC / precio. Markup % = MC / costo variable. Fixed costs are NOT part of the per-product verdict (they are paid by the whole business).
- S4 Verdict codes: `NO_CUBRE_VARIABLE` (MC <= 0), `MC_BAJO` (MC % below a threshold; threshold is optional and disabled by default), `SALUDABLE`. SUPUESTO: threshold value pending, not invented.
- S5 Pure Decimal engine in costeo.py (no db, no clock); the backend is the only one that calculates.
- S6 (later, not in this PR) U5 screens.
- S7 Pure engine `equilibrio_con_mezcla(fijos, mezcla)` in costeo.py. `mezcla` = list of `ProductoEnMezcla(precio, variable_por_unidad, unidades)` (all Decimal). Weighted MC % = sum(MC unit x units) / sum(precio x units) x 100. equilibrio_ingresos = fijos / (MC% / 100), exact Decimal, no rounding. equilibrio_unidades = ceil(total_units x equilibrio_ingresos / ingresos) (same mix, scaled). utilidad = MC total - fijos. margen_seguridad_pct = (ingresos - equilibrio_ingresos) / ingresos x 100. Returns a dataclass with a `motivo`: `SIN_VENTAS` (empty mix or revenue 0) or `MC_NO_POSITIVO` (total MC <= 0) and then the number fields are None; never a number in those cases. Fixed costs are global, NEVER spread over products. SUPUESTO: validar (volume is a scenario typed by the owner, not sold units).
- S8 `POST /productos/{codigo}/precio-venta` (same auth as other writes, ESCRITURA) stores a row in `precio_venta` (body: precio_ars > 0, vigente_desde default today, nota optional; creado_por = current user id as text when available). `GET /productos/{codigo}/precio-venta` lists the history, newest first. Unknown product -> 404 via NoEncontrado. Never UPDATE/DELETE.
- S9 `GET /productos/{codigo}/rentabilidad?precio=`: variable cost = today's total cost of the product from the existing `_costos_totales_de_hoy`; price = `precio` query if given (fuente `INGRESADO`) else the latest saved precio_venta (fuente `GUARDADO`) else `motivo: SIN_PRECIO`. If the cost cannot be computed -> `motivo: SIN_COSTO_VARIABLE`. Otherwise returns `margen_de_contribucion` fields (margen_unidad, margen_pct, markup_pct, veredicto). Money as Decimal. Does not persist.
- S10 `POST /cvu/escenario` body `{periodo?: "AAAA-MM", items: [{codigo, unidades > 0, precio?}]}`: fixed costs = FABRICA fixed of the period (default current month) via existing `_fijos_de_fabrica`; per item price = given or latest saved; items without price or cost go to `omitidos` with a motivo and are not computed. Returns the S7 result, per-item lines (contribucion total and share of total MC), `omitidos`, and `avisos` reusing codes FIJOS_PENDIENTES, FIJOS_FICTICIOS, SIN_FIJOS plus `VOLUMEN_ESCENARIO` ("El volumen es el que cargaste, no ventas reales."). If fixed costs are missing, pending or fictitious the result carries `confiable: false`. Does not persist.
- S11 Every number is computed by the backend as Decimal; response models follow `Salida` in api.py.

## Tasks

- [x] T1 (S2) `PrecioVenta` model + migration 0006 + tests (models, migration chain, verification lists). Route: inline. Commit 8e08a61. Check: 1135 passed, 150 skipped; migration not applied to a real PostgreSQL (no local DB).
- [x] T2 (S3, S4, S5) `margen_de_contribucion` in costeo.py + tests. Route: inline. Commit 17e7478. RED observed (ImportError), then GREEN.
- [ ] T3 (S7) `equilibrio_con_mezcla` pure engine + tests (RED first). Route: delegated (context backstop).
- [ ] T4 (S8, S9, S10, S11) service functions + endpoints + tests (store, history, rentabilidad, escenario). Route: delegated (context backstop).

## Log

- L1 (2026-11-05) Original request: "como podemos hacer para que el dueno de negocio en base a todo lo que hicimos una vez que ponga el precio pueda ver si le esta siendoi rentable o no en base al framework CVU"
- L2 (2026-11-05) Agreed plan v2: "MC por producto + equilibrio global con mezcla de ventas escenario"; user approved starting with U1 and U2 ("si").
