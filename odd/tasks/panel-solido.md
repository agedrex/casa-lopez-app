# Panel sólido: corregir costos, tendencia y datos de ejemplo

Objective: let the user correct fixed costs (factory and personnel) without duplicates, copy last month, see a 6-month trend of how the business is performing, and have synthetic data to try it. Costs only; sale price stays a typed simulator input.
Branch: feat/panel-solido (from main after PR #12/#13). Delivery: chained PRs per slice (user chose chained PRs before). Runner: backend `.venv/bin/python -m pytest -q`; front biome + tsc.

## Specs

- S1 A fixed cost can be corrected: the correction is a NEW row that replaces the previous one; the old row is kept (nothing is deleted) and no longer counts in any total. Applies to FABRICA and TIENDA rows and to salaries (categoria SUELDOS). DER change approved by the user ("Sí, aprobado"): nullable `gasto_periodo.reemplaza_a_id`.
- S2 "Copiar el mes anterior": creates the month's rows from the previous month's current rows (same concept, category, side, person); refuses if the target month already has rows.
- S3 Trend: last 6 months, per month: fixed FABRICA, units produced, variable cost per unit, fixed per unit, total per unit; months with missing data are shown with a reason, never hidden or broken (a "solid" panel).
- S4 Synthetic data: 6 months of lots, salaries/fixed costs, dollar and prices, every row flagged as example (`ficticio`/note), loaded by an idempotent script that goes through `servicios` functions. Loading it into staging needs the user's explicit authorization first.
- S5 Money only computed by the backend (Decimal strings). Plain Spanish UI for non-technical users.
- S6 Every total that reads gasto_periodo (costos_fijos, panel, sheets export, calidad) ignores replaced rows.

## Tasks

- [x] T1 (S1, S2, S6) Migration 0005 + correct/copy endpoints + totals ignore replaced rows + tests. Route: delegated. RISK: item 1 (migration, persisted format) -> own commit + independent verifier. DONE: commit 894eca1; independent verifier: S1,S2,S6 pass, no blockers (1189 passed with PostgreSQL, 1060 passed/129 skipped without).
- [x] T2 (S3) Trend endpoint and panel robustness (backend). Route: delegated. DONE: 1097 passed/141 skipped without DB; 1238 passed with local PostgreSQL.
- [x] T3 (S4) Synthetic data script (idempotent) + local test. Route: delegated. DONE: script + 33 tests; 1121 passed/150 skipped without DB, 1271 passed with local PostgreSQL. Not loaded anywhere remote.
- [x] T4 (S1-S3, S5) Front: correct/copy UI in costos-fijos, trend block in the panel. Route: delegated. DONE: biome, tsc, next build clean; not seen on screen, actions not tried against the backend.
- [ ] T5 (S4) Load examples into staging — only after the user authorizes it. Route: inline.

## Log

- L1 (2026-11-04) "me gusta el panel pero quiero algo mas fijo y que empieces a crear datos sinteticos de como se usaria y se veria. La idea es que, tanto en la parte personal como en costos de fábrica y todo eso, lo hagamos de manera que el mismo usuario pueda actualizar e ir cambiando ciertas variables. Y que después pueda ver realmente cómo está rindiendo el negocio"
- L2 (2026-11-04) "más fijo" = "Más sólido" (chosen by the user).
- L3 (2026-11-04) DER change approved: "Sí, aprobado".
