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

- `GET http://localhost:8000/api/health`
- `GET http://localhost:8000/api/demo/resources`

Start the frontend in another terminal:

```sh
cd front
corepack pnpm dev
```

Open <http://localhost:3000>. The frontend reads the API server-side from `API_URL` (default `http://127.0.0.1:8000` outside production); the browser never calls the API directly. See [Authentication](#authentication-and-environment-variables) for the variables the app needs to sign in.

The API includes PostgreSQL connection/session support through `DATABASE_URL`. See [backend configuration and the internal connection check](backend/README.md#postgresql-connection). Demo endpoints still return fictional data; no DER tables or migrations have been added.

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

`front/.env.example` lists the frontend ones; copy it to `front/.env.local` for local work.

```sh
cd front
corepack pnpm auth:migrate   # creates the Better Auth tables in `public` (needs DATABASE_URL, BETTER_AUTH_SECRET)
SEED_USER_PASSWORD='choose-a-password' corepack pnpm seed:user   # creates contacto@agedrex.com (admin); safe to re-run
```

`auth:migrate` applies changes to whatever database `DATABASE_URL` points to, so check that variable before running it against a shared environment. The backend verifier forwards the `Cookie` (and `Authorization`) header to `AUTH_VERIFY_URL` with a 3 second timeout and answers `401 No autenticado.` on any failure.

Roles (stored in `user.role`): `admin` (everything, plus `/admin` and user management), `cotizador` (quotes and loads data) and `consulta` (read only). New users get `consulta`. This task enforces `/admin` for admins only; per-module permissions for the other roles arrive with the modules themselves.

## Checks

```sh
uv run --directory backend pytest -q
cd front && corepack pnpm lint && corepack pnpm build
```

## Deployment (Railway)

Push tested changes directly to `main`; no issue or pull request is required. GitHub Actions runs backend tests and frontend lint/build on each push. Railway waits for those checks before deploying the frontend (`front/`) and API (`backend/`) to **staging**. Failed checks skip the staging deployment, but do not block the commit from landing on `main`.

- Frontend: <https://frontend-staging-8dc6.up.railway.app/>
- API health check: <https://backend-staging-566d.up.railway.app/api/health>

Verify the change in staging before promoting it. Production does **not** deploy automatically; promote only after explicit approval. The current production services have not had a successful deployment yet; after staging is verified, deploy the same tested commit to production and smoke-test both URLs. Railway variables and domains are already configured separately for each environment. Demo endpoints work without a database; PostgreSQL access uses the backend's `DATABASE_URL` reference.

`main` remains directly writable without PRs; the checks gate Railway's staging deployment, not the GitHub commit itself. Do not enable Railway production auto-deploy.
