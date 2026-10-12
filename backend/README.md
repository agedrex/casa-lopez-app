# Casa Lopez demo API

Run the local API from the repository root:

```sh
uv run --directory backend fastapi dev src/backend/main.py --host 127.0.0.1 --port 8000
```

The API exposes health and fictional demonstration resources. It is not a costing or quoting service.

For deployed frontends, set `CORS_ALLOWED_ORIGINS` to a comma-separated list of exact origins, for example `https://frontend-staging.example.com`. `http://localhost:3000` is always allowed for local development; wildcard entries are ignored.

## PostgreSQL connection

The backend uses SQLAlchemy 2 with the psycopg 3 driver. Set `DATABASE_URL` through the environment's secret configuration; never put credentials in source code, shell commands, or logs. Railway staging already supplies this variable through its Postgres service reference.

`database.py` reads and validates the URL when the application starts. It accepts `postgres://`, `postgresql://`, and `postgresql+psycopg://`, selects psycopg, and preserves URL options such as `sslmode`. Engine creation does not connect to PostgreSQL. Connections open only when a session executes a query or the check command runs, with a 10-second connection timeout.

The demo can still start without `DATABASE_URL`. Database access requires a valid URL with a host and database name. Invalid configuration produces fixed messages that do not include credentials.

## Check connectivity

After `DATABASE_URL` is securely provided for an authorized local test database or staging environment, run from the repository root:

```sh
uv run --directory backend python -m backend.db_check
```

The command executes only `SELECT 1`, closes the connection, and disposes the engine. It prints a fixed result and exits with code `0` on success or `1` on failure. It does not create tables, run migrations, or change data. It adds no HTTP route; `/api/health` remains a demo application check and does not verify the database.

Before running this command through Railway, request explicit authorization for the staging backend service and its configured environment. Do not run it in production or print/export the connection URL. No Railway check or deployment is part of this repository change.

## Sessions and tests

Future database endpoints can use `Depends(get_session)` from `backend.database`. Each request gets a session; cleanup closes it and rolls back uncommitted work. Writes must call `session.commit()` explicitly. The application disposes its engine at shutdown. No DER models or migrations exist yet.

```sh
uv run --directory backend pytest -q
uv lock --check --directory backend
```

Tests replace or remove `DATABASE_URL` and use mocks or in-memory SQLite. They never connect to Railway or production.
