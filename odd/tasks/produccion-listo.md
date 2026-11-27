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
- T5 (S8): dollar cron. Route: inline after T1-T4. Commit: done — running in production as the `dolar-cron-production` service with schedule `0 12 * * 1-5` [V: 2026-11-27]

## Estado verificado (2026-11-15)

Contra el código: healthcheck real con 503 sin base (`main.py`), `/db/estado` solo admin, CI con Postgres 16, cabeceras de seguridad en `front/next.config`. Pendiente fuera del código: backups en Railway, cron del dólar, valores reales (margen de transferencia, `GASTOS_VENTA_PCT`, IIBB, costos fijos), y el deploy a production con backup y autorización.

## Estado verificado (2026-11-27)

Contra Railway y la base de production, no contra el código:

- **Promoción hecha:** los tres servicios de production (`backend`, `frontend`, `dolar-cron-production`) corren el commit `1662253`, igual que staging, y la base pasó de `0025_proveedor_material` a `0026_orden_estado_cambiado_por` (head) con el pre-deploy. Health del backend 200 y `/login` del frontend 200. Respaldo `pg_dump` previo verificado por SHA.
- **S8 cerrada:** el cron del dólar corre con schedule `0 12 * * 1-5` y hay 10 cotizaciones en la base.
- **Backups: siguen sin activar y no se pueden activar por código.** Ni el CLI, ni el MCP, ni la API pública ofrecen una mutación para crear un schedule, y escribir `backupSchedules` en el mount del volumen no queda en la config live (se intentó el 2026-11-10 y el 2026-11-27). Es un clic de una persona en el dashboard. El procedimiento manual con `pg_dump`, ya probado, quedó en `docs/produccion.md` sección 6B.
- **La base de production tiene solo catálogos y usuarios, y es lo esperado** (confirmado por el usuario): no se cargan las semillas de modelos ni materiales.
- **Sigue pendiente, fuera de este trabajo:** rotar la credencial de admin de staging, observabilidad, y pasar `railway.toml` a Infrastructure as Code antes del 2026-12-01.
- **Hallazgo nuevo, sin resolver:** `pnpm build` del frontend aborta el **primer** intento con `SecurityFatalError` porque Next.js 16.4.3 tiene una vulnerabilidad conocida; el reintento pasa. No bloquea el CI ni el deploy de Railway, pero el aviso de actualizar Next sigue en pie.

## Log
- L1 (2026-11-10): "hagamos todo eso antes de empezar una nueva sesion" — referring to the list: backups, probar production logueado, rotar credenciales, healthcheck real, cerrar `/db/estado` y rutas demo, cabeceras de seguridad, CI con Postgres, errores en producción, cron del dólar, filtros de la interfaz de productos, AGENTS.md desactualizado y limpieza de worktrees.
- L2: Route declaration: T1+T2 and T3 are independent units with disjoint edit surfaces, each several files, launched together (Writer rule a). T4 is small and runs inline.
