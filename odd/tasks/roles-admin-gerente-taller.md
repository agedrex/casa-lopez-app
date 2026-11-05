# Roles: Admin, Gerente, Taller

Objective: replace the roles admin/cotizador/consulta/corte with three roles and gate data by role (deny by default).
Branch: feat/roles-admin-gerente-taller (from main). Delivery: 2 PRs (backend, front) ask-on-risk; auth is high risk (item 2). Test runner: backend `.venv/bin/python -m pytest -q`; front `./node_modules/.bin/tsc --noEmit` and `./node_modules/.bin/biome check .`.

## Specs

- S1 "debemos tener tres roles principales Admin, Gerente y Taller, Admin con acceso a todo, gerente con acceso mas restingido, solo a cuento se cotizo el producto y Taller solo acceso a voz y no mucho mas". (L1)
- S2 Mapping decided by the user (option A): `cotizador` -> admin, `corte` -> taller, `consulta` -> gerente. It is applied when roles are READ, in the backend (`Usuario.roles`) and the front (`parseRoles`), so existing users keep access with NO database update. A user with several comma-separated roles gets the union. Unknown role names are still dropped.
- S3 Backend access, deny by default:
  - admin: everything (all reads and writes), user management included.
  - gerente: read-only. Allowed GETs: `/productos`, `/productos/{codigo}`, `/productos/{codigo}/rentabilidad`, `/productos/{codigo}/precio-venta`, `/grilla`, plus any other GET that is strictly product + quote data (list them in your return for review). Every other endpoint (fixed costs, panel, trend, orders, fabrication, dollar, material prices, quality, sync, `POST /cvu/escenario`, parameters) is admin only. No writes.
  - taller: the voice endpoints (`/voz/estado`, `POST /voz/interpretar`), the cut endpoints (`POST /cueros/{codigo}/cortes`, `/sobrante`) and the GETs the corte/cueros/voz pages call (decided after the T1 heads-up, L3): `/ordenes` list and detail, `/productos` list and the cueros reads, so taller keeps everything the old `corte` role did. No costs, prices or fixed costs. SUPUESTO: validar. Known limitation: the cueros GET responses carry the price paid per m2; report it, do not change the response contract.
  - `POST /productos/{codigo}/precio-venta` and every other write: admin only.
- S4 Front: `ROLES = admin, gerente, taller`; labels Administrador, Gerente, Taller; `DEFAULT_ROLE = gerente` (SUPUESTO: keeps the previous default consulta). Nav: admin as today's admin; gerente sees Productos (and Grilla); taller sees Voz, Corte and Cueros. A role that opens a path it may not reach is redirected to its home (gerente: /productos, taller: /corte or /voz). `canWrite` is admin only, so the save-price button and every form is admin only. The admin user forms offer the three roles. `/admin` stays admin only.
- S5 Tests: existing tests that name roles are updated to the new names; add tests for the legacy aliasing (S2), for deny-by-default (gerente and taller refused on a representative set including `/panel/costos`, `/costos-fijos`, `POST /cvu/escenario`, `/ordenes`) and for the allowed sets.
- S6 Out of scope: any UPDATE of `public."user"` (Alembic never touches Better Auth tables), deploy, and the sales price list view.

## Tasks

- [x] T1 (S2, S3, S5) backend roles + gates + tests. Route: delegated (parallel unit). Commit d954144. RED: 35 failed. Check: 1343 passed/151 skipped without DB; 1494 passed with a throwaway PostgreSQL (parent run).
- [x] T2 (S2, S4) front roles, nav, guards, admin forms. Route: delegated (parallel unit). Commit a6113d9. tsc 0, biome clean; NO visual check.

## Log

- L1 (2026-11-05) User: "debemos tener tres roles principales Admin, Gerente y Taller, Admin con acceso a todo, gerente con acceso mas restingido, solo a cuento se cotizo el producto y Taller solo acceso a voz y no mucho mas"
- L2 (2026-11-05) Context: the user wants a salesperson to see price/profitability in a list view (later). Question "cotizador y corte desaparecen (A) o conviven (B)": user answered "A".
- L3 (2026-11-05) T1 writer found that front corte/page.tsx reads GET /ordenes and /productos. Decision: taller keeps what the old corte role could do (S3 amended); the response bodies of those GETs are reviewed for money fields afterwards.
- L4 (2026-11-05) Open: what taller may confirm by voice (A none / B only registrar_precio_taller / C all). Today taller can interpret but not confirm. Also open: taller reads /ordenes, /productos and /cueros bodies that carry money.
- L5 (2026-11-05) User chose B for the voice: taller confirms by voice only `registrar_precio_taller` (POST /ordenes/{codigo}/items/{item}/precios now admin+taller); dollar, material prices, extras and fixed costs stay admin only. RED: test_every_route_has_exactly_the_documented_roles failed against the old gate, then green; 1335 passed/151 skipped, tsc 0, biome clean.
