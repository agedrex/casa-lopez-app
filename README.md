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

## Checks

```sh
uv run --directory backend pytest -q
cd front && corepack pnpm lint && corepack pnpm build
```
