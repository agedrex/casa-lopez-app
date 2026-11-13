# Casa López prototype

This repository contains the initial discovery prototype described by La Fábrica `WO-4`. It demonstrates a Next.js frontend connected to a FastAPI JSON API.

> **Prototype only:** displayed resources are fictional. This application is not a source for real quotations, costs, or business decisions. Costing formulas and production data models remain unvalidated and are intentionally not implemented.

## Requirements

- Node.js and Corepack (for pnpm)
- Python 3.13+
- `uv`

## Run locally

Start the API in one terminal:

```sh
uv run --directory backend fastapi dev src/backend/main.py --host 127.0.0.1 --port 8000
```

The API provides:

- `GET http://localhost:8000/api/health` (answers 200 only when the database responds, 503 otherwise)

Start the frontend in another terminal:

```sh
cd front
corepack pnpm dev
```

Open <http://localhost:3000>. The frontend reads the API server-side from `API_URL` (default `http://127.0.0.1:8000` outside production); the browser never calls the API directly. See [Authentication](#authentication-and-environment-variables) for the variables the app needs to sign in.

The API includes PostgreSQL connection/session support through `DATABASE_URL`. See [backend configuration and the internal connection check](backend/README.md#postgresql-connection). The schema (DER v3) is created by the Alembic migrations in `backend/migrations`; see `AGENTS.md` for the current model.

## Authentication and environment variables

Sign-in is handled by [Better Auth](https://better-auth.com) inside the Next.js app (email and password, session cookie, public sign-up disabled). Its four tables (`user`, `session`, `account`, `verification`) live in the `public` schema of the same Postgres database; Alembic only manages the `costos` schema and never touches them. The costing API trusts a request only if the Next.js app confirms the session.

| Where | Variable | What it is |
|---|---|---|
| front | `DATABASE_URL` | Postgres for Better Auth. Plain `postgresql://` URL (no `+psycopg`). |
| front | `BETTER_AUTH_SECRET` | Long random secret (`openssl rand -base64 32`). Never commit it. |
| front | `BETTER_AUTH_URL` | Public URL of the frontend, no trailing slash. |
| front | `API_URL` | Server-only base URL of the API. |
| front | `SEED_USER_PASSWORD` | Only for `seed:user`; required by that script. |
| backend | `AUTH_VERIFY_URL` | `<BETTER_AUTH_URL>/api/auth/get-session`. If unset, every protected route answers 401 (fail-closed). |
| backend | `GOOGLE_SHEETS_SPREADSHEET_ID` | Optional. Id of the Google Sheet that receives the display copy (see [`docs/sheets-sync.md`](docs/sheets-sync.md)). |
| backend | `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional. Content of the service account key (JSON, not a path). Never commit it. Without both Google variables only dry runs work. |
| backend | `AI_GATEWAY_API_KEY` (or `ANTHROPIC_API_KEY`) | Optional. Key of the model (Vercel AI Gateway preferred) that interprets the voice screen (see [`docs/voz.md`](docs/voz.md)). Without it `/voz/interpretar` answers 503. Never commit it. |
| backend | `VOZ_LLM_MODEL` | Optional. Default `claude-haiku-5-5`. (`VOZ_LLM_BASE_URL` exists only for tests.) |

`front/.env.example` lists the frontend ones; copy it to `front/.env.local` for local work.

```sh
cd front
corepack pnpm auth:migrate   # creates the Better Auth tables in `public` (needs DATABASE_URL, BETTER_AUTH_SECRET)
SEED_USER_PASSWORD='choose-a-password' corepack pnpm seed:user   # creates contacto@agedrex.com (admin); safe to re-run
```

`auth:migrate` applies changes to whatever database `DATABASE_URL` points to, so check that variable before running it against a shared environment. The backend verifier forwards the `Cookie` (and `Authorization`) header to `AUTH_VERIFY_URL` with a 3 second timeout and answers `401 No autenticado.` on any failure.

Roles (stored in `user.role`): `admin` (everything, plus the `/admin` area and user management), `gerente` (read only: products, models and the scenario simulator) and `taller` (a workshop: sees the products list with costs, cuts and confirms its own price by voice). The legacy names `cotizador`, `consulta` and `corte` are still read and mapped to `admin`, `gerente` and `taller`. New users get the default role defined in `front/lib/permissions.ts`; sign-up is disabled, an admin creates users in `/admin/usuarios`.

The admin area (`/admin/*`: users, taxes, Google Sheet; `/admin` redirects to users) is `admin` only, and so are the models and catalogs that moved to Productos (`/productos/modelos`, `/productos/catalogos`) and the people panel of Costos fijos > Mano de obra, at three levels: `proxy.ts` redirects everybody else, every server action re-checks the role, and the API answers 403 to the admin-only writes (see the table in [`backend/README.md`](backend/README.md#costing-api-t3b)). Users are never deleted, only deactivated; nobody can demote or deactivate themselves, and the last active admin can never lose the role (enforced inside Better Auth, so a direct call to `/api/auth/admin/*` is refused too).

## Consumption forms

`/formularios` holds the digital "formulario de consumos y herrajes" of each new article (admin creates and validates, the `taller` role fills it in). It does no costing; the flow, buttons and print-to-PDF are described in [`docs/formularios.md`](docs/formularios.md).

## Checks

```sh
uv run --directory backend pytest -q
cd front && corepack pnpm lint && corepack pnpm build
```

## Deployment (Railway)

Push tested changes directly to `main`; no issue or pull request is required. GitHub Actions runs backend tests and frontend lint/build on each push. Railway waits for those checks before deploying the frontend (`front/`) and API (`backend/`) to **staging**. Failed checks skip the staging deployment, but do not block the commit from landing on `main`.

- Frontend: <https://frontend-staging-8dc6.up.railway.app/>
- API health check: <https://backend-staging-566d.up.railway.app/api/health>

Verify the change in staging before promoting it. Production does **not** deploy automatically; promote only after explicit approval. After staging is verified, deploy the same tested commit to production by hand (`railway redeploy -e production -s <service> --commit <SHA> -y`, run from the main checkout) once a database backup is verified, and smoke-test both URLs. See [`docs/produccion.md`](docs/produccion.md) for the checklist, rollback and backups. Railway variables and domains are already configured separately for each environment. Demo endpoints work without a database; PostgreSQL access uses the backend's `DATABASE_URL` reference.

`main` remains directly writable without PRs; the checks gate Railway's staging deployment, not the GitHub commit itself. Do not enable Railway production auto-deploy.
