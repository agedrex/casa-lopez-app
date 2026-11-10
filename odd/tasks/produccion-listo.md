# Production readiness: remaining hardening

Objective: close the open items of the production audit that code can close. Delivery strategy: ask-on-risk, one PR per task to `main` (staging auto-deploys gated by CI; production is manual with `railway redeploy -e production -s <svc> --commit <SHA> -y`, run from the main checkout, which is the one linked to Railway). Test runner: `cd backend && uv run pytest -q`; front: `pnpm lint && pnpm build`.

## Specs
- S1: "Healthcheck real que mire la base": `/api/health` must answer 503 when the database cannot be reached and 200 when it can; the response must not say `"mode": "demo"`. Railway uses it as `healthcheckPath`, so it must stay public, fast (short DB timeout) and must not leak revision, table counts, hosts or errors.
- S2: "Cerrar lo público": `/db/estado` (shows the Alembic revision and table count without a session) must require the admin role; `/api/demo/resources` is removed. `/api/health` and `/catalogo/etapas` stay as they are. The roles matrix test (`test_roles.py`) must still pin exactly the public and gated routes.
- S3: "Cabeceras de seguridad": the frontend sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, a restrictive `Permissions-Policy`, and a Content-Security-Policy that keeps the app working (Next.js inline scripts/styles, the API origin, voice/microphone use); HSTS is left to Railway.
- S4: "CI con Postgres": the GitHub Actions backend job runs the integration tests against a Postgres service container (`TEST_DATABASE_URL`), so the 15+ skipped integration tests run on every push.
- S5: "Filtros sin cuero, sin color y estado" in the product list: optional `sin_cuero=true`, `sin_color=true` and `estado=<EN_DEFINICION|COTIZADO|EN_PRODUCCION|PRODUCIDO>` query params on `GET /productos` and `GET /productos/conteo`, shared by list and count; without them the previous behavior does not change; controls in the list's search form.
- S6: "AGENTS.md desactualizado": AGENTS.md must reflect the v3 model that is in production (modelo/producto/cotizacion, GG and parity decisions per `odd/tasks/app-casa-lopez-v3.md`), the production facts (envs, deploy commands, pre-deploy migrations, guards of the importer) and the working-tree rule that Railway commands run from the main checkout. Do not invent business rules; mark assumptions.
- S7: "Limpieza": remove local worktrees whose branches are already merged into `main` (never one with uncommitted changes) and delete their merged local branches.
- S8: "Cron del dólar": the BNA dollar update runs on a schedule (Railway cron) so `costo de hoy` does not depend on typing it by hand. Needs an infrastructure decision; done after S1-S7.
- Out of scope / needs the user: enabling Postgres backups in the Railway dashboard, logging into production to check the UI, rotating the staging admin credential, Gerardo's open questions, error tracking (needs an external account).

## Tasks
- T1 (S1, S2): backend hardening. Route: delegated (parallel unit, worktree `hardening-backend`). Commit: pending
- T2 (S4): CI with Postgres. Route: delegated with T1 (same worktree, `.github/workflows/ci.yml`). Commit: pending
- T3 (S3, S5): security headers and product filters. Route: delegated (parallel unit, worktree `productos-filtros`). Commit: pending
- T4 (S6, S7): docs and cleanup. Route: inline (worktree `docs-limpieza`). Commit: pending
- T5 (S8): dollar cron. Route: inline after T1-T4. Commit: pending

## Log
- L1 (2026-11-10): "hagamos todo eso antes de empezar una nueva sesion" — referring to the list: backups, probar production logueado, rotar credenciales, healthcheck real, cerrar `/db/estado` y rutas demo, cabeceras de seguridad, CI con Postgres, errores en producción, cron del dólar, filtros de la interfaz de productos, AGENTS.md desactualizado y limpieza de worktrees.
- L2: Route declaration: T1+T2 and T3 are independent units with disjoint edit surfaces, each several files, launched together (Writer rule a). T4 is small and runs inline.
