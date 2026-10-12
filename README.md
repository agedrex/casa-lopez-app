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

Open <http://localhost:3000>. The frontend defaults to `http://localhost:8000`; to use another API origin, set `NEXT_PUBLIC_API_URL` in the frontend environment before starting the dev server.

The API includes PostgreSQL connection/session support through `DATABASE_URL`. See [backend configuration and the internal connection check](backend/README.md#postgresql-connection). Demo endpoints still return fictional data; no DER tables or migrations have been added.

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
