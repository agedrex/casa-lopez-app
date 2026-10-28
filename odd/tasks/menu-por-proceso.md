# Process-oriented navigation

## Objective

Make the desktop sidebar and mobile navigation follow Casa López's work sequence. Show each role its most useful mobile shortcuts while preserving existing permissions and destinations.

Branch: `feat/menu-por-proceso` (from `main`). Delivery: one PR against `main`; do not merge or push to `main`.

Engram mirror: pending. `mem_save` was rejected by the PreToolUse hook because the Codex host session is not registered; the local task document remains the recovery source until the host issue is resolved.

## Scope and constraints

- Group navigation in this order: `Resumen`, `1 · Datos de base`, `2 · Productos y costos`, `3 · Producción`, `4 · Fin de mes`, `Consultas`, `Control`, `Herramientas`.
- Surface the existing `/admin/modelos` page in the main navigation and keep its Administration entry.
- Add `Grilla completa` and `Histórico (Excel viejo)` destinations using the existing coming-soon component.
- SUPUESTO: use `/grilla` and `/historico` as the new route paths because the request names the destinations but does not prescribe URLs.
- Define mobile shortcuts centrally in `front/lib/nav.ts`: admin and cotizador get Panel, Productos, Precios, Lotes; consulta gets Panel, Grilla, Productos, Alertas. The fifth mobile item is `Más`, which reveals all allowed entries in the same groups.
- Update user-visible `Tablero` and `Calidad de datos` references; keep the `/calidad` URL and existing role permissions.
- Interface copy is simple Rioplatense Spanish. Reuse the existing components, Casa López branding, typography, and colors.
- No DER edits, Alembic migrations, new roles, backend cost calculations in the frontend, Railway changes, or staging operations. Backend `Decimal` values remain API-provided strings in the frontend.

## Task and acceptance

- [ ] **T1 — Deliver process-oriented navigation and page copy.** Rework the shared navigation data and desktop/mobile renderers, add both coming-soon pages, and update the requested labels in page titles, breadcrumbs, and links. Verify that all existing allowed pages remain reachable, that Administration is admin-only, that shortcuts match each role, and that the mobile page has no horizontal scrolling.

Route: delegated direct. Trigger evidence: implementation requires coordinated non-trivial edits across navigation data, renderers, routes, and user-visible copy; reading those files prepares the write.

Test-first policy: use a focused deterministic RED check if the existing test infrastructure offers one for navigation behavior. Otherwise record that exception and verify rendered behavior directly. Keep any relevant tests with T1's work-unit commit.

Observed exception: the frontend has no navigation test runner or existing focused navigation test. The route and role behavior was checked by source inspection and production TypeScript compilation; browser verification remains pending.

## Verification

- [ ] `uv run --directory backend pytest -q`
- [ ] `cd front && corepack pnpm lint`
- [ ] `cd front && corepack pnpm build`
- [ ] Inspect admin, cotizador, and consulta navigation and destination access in the browser.
- [ ] Capture 375 px and desktop screenshots for the PR; at 375 px confirm touch targets are at least 44 px and the page does not scroll horizontally (wide tables scroll within their container).
- [ ] Record any skipped or failed check and every `SUPUESTO` in the PR.

## Delivery and progress

Forecast: 250–400 authored changed lines, excluding generated files. Strategy: `single-pr`, based on the user's request for one PR; reassess before commit if the implementation materially exceeds the forecast. Running authored line count: pending. Slice: one PR containing T1's work-unit commit. Commit identity, native assessment, screenshots, PR URL, and final verification results: pending.

Implementation progress: grouped desktop and mobile navigation, role-specific tabs, both coming-soon routes, and requested page labels are written. T1 stays open until required checks and visual acceptance are resolved.

Scoped correction: the shared active-state function now selects the longest matching navigation path. On `/admin/modelos` and its children, only `Modelos` is current; `/admin` and its other children keep `Administración` current. This also keeps the mobile `Más` state consistent.

Verification observed:

- The exact backend command could not start because `uv` is absent from PATH. The known local `uv.exe` path does not exist, and the installed `backend/.venv/Scripts/pytest.exe` points to a missing Python executable.
- `corepack pnpm lint` started downloading missing packages; it was stopped to avoid an uncoordinated install. Direct installed Biome checked the 12 modified frontend files successfully. Whole-tree direct Biome found 96 formatting errors in files outside this task, mainly CRLF line endings.
- Direct installed Next build passed on the second invocation, including TypeScript and both new routes. The first invocation stopped for Next's security upgrade reminder. Installed Next reports version 16.4.0 and a known vulnerability; no upgrade was performed. Better Auth reported missing local base URL and default secret during prerender, without failing the second build.
- `git diff --check` passed. The browser role check and 375 px / desktop screenshots remain pending because the browser control host is unavailable.
- Scoped active-state correction: `node node_modules/@biomejs/biome/bin/biome format --write components/main-nav.tsx` completed; `node node_modules/@biomejs/biome/bin/biome check components/main-nav.tsx` passed (1 file, no fixes). A single direct installed Next build compiled and typechecked, generated all 31 pages, then exited 1 at the existing Next 16.4.0 `SecurityFatalError` upgrade reminder. No package change was made.

Next step: restore a working local backend runner and frontend dependencies for the exact checks, inspect the three role menus at 375 px and desktop, capture screenshots, then commit the verified work unit and open the PR against `main` without merging it.
