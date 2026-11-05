# CVU: rentabilidad del precio de venta

Objective: the owner types a sale price and sees if it is profitable following cost-volume-profit (contribution margin first, break-even with sales mix later).
Branch: feat/panel-cvu. Delivery: single PR for U1+U2 (ask-on-risk). Test runner: backend `.venv/bin/python -m pytest -q`.

## Specs

- S1 "Cuando ponga el precio pueda ver si le está siendo rentable o no en base al framework CVU". (L1)
- S2 The sale price is stored with a date, append-only (no UPDATE): table `precio_venta`. This reverses the earlier panel-costos S1 ("never stored"), requested in L1/L2. Money is ARS only (`precio_ars`).
- S3 Contribution margin per unit = precio - costo variable por unidad. MC % = MC / precio. Markup % = MC / costo variable. Fixed costs are NOT part of the per-product verdict (they are paid by the whole business).
- S4 Verdict codes: `NO_CUBRE_VARIABLE` (MC <= 0), `MC_BAJO` (MC % below a threshold; threshold is optional and disabled by default), `SALUDABLE`. SUPUESTO: threshold value pending, not invented.
- S5 Pure Decimal engine in costeo.py (no db, no clock); the backend is the only one that calculates.
- S6 (later, not in this PR) U3 global break-even with sales mix, U4 endpoints, U5 screens.

## Tasks

- [x] T1 (S2) `PrecioVenta` model + migration 0006 + tests (models, migration chain, verification lists). Route: inline. Commit 8e08a61. Check: 1135 passed, 150 skipped; migration not applied to a real PostgreSQL (no local DB).
- [x] T2 (S3, S4, S5) `margen_de_contribucion` in costeo.py + tests. Route: inline. Commit 17e7478. RED observed (ImportError), then GREEN.

## Log

- L1 (2026-11-05) Original request: "como podemos hacer para que el dueno de negocio en base a todo lo que hicimos una vez que ponga el precio pueda ver si le esta siendoi rentable o no en base al framework CVU"
- L2 (2026-11-05) Agreed plan v2: "MC por producto + equilibrio global con mezcla de ventas escenario"; user approved starting with U1 and U2 ("si").
