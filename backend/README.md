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

Database endpoints use `Depends(get_session)` from `backend.database`. Each request gets a session; cleanup closes it and rolls back uncommitted work. Writes must call `session.commit()` explicitly. The application disposes its engine at shutdown.

```sh
uv run --directory backend pytest -q
uv lock --check --directory backend
```

Tests replace or remove `DATABASE_URL` and use mocks or in-memory SQLite. They never connect to Railway or production.

## DER v3 schema and migrations

The 25 DER v3 models are in `src/backend/models.py` (summary in [`docs/der-v3.md`](../docs/der-v3.md); the v1 design in `docs/der.md` is superseded). All application tables
and Alembic's version table live in `costos`; Alembic excludes `public`, reserved
for Better Auth. Revisions: `0001`/`0002` (v1, kept for history), `0003_der_v3`
(drops the v1 tables with `IF EXISTS`, creates v3) and `0004_semillas_v3` (reference
data from the plantilla). They run only explicitly, never at application startup.
Downgrading `0003` drops v3 only; v1 is not recreated.

The seeds come from `migrations/seed_data/seed_v3.json`, generated from the xlsx by
`scripts/generate_seed_v3.py` (not run by migrations; see its docstring).

After the project's declared dependencies are available, supply `DATABASE_URL`
securely for an authorized disposable local PostgreSQL. From `backend/`:

```sh
uv run alembic upgrade head --sql
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run python -m backend.verificar_db
uv run python -m backend.verificar_db --prueba-escritura
```

The verification script checks revision, tables, seed counts and the seeded business
keys (including the blocked exotic leathers). Optional write probes use savepoints
inside one transaction that always rolls back. It refuses Railway environments other
than `staging`. No credentials or connection diagnostics are printed.

`GET /db/estado` returns the current revision and application table count;
`GET /catalogo/etapas` returns the ordered stage catalog (code, order, type, always-applies, treatment).
These endpoints only read and expose no prices. Database failures return a generic 503.

Run tests from the repository root with `uv run --directory backend pytest -q`.
The thirteen PostgreSQL integration cases (ten constraint probes, seed validation, head
tables/counts and the seed downgrade) skip unless `TEST_DATABASE_URL` is explicitly
supplied for a disposable local PostgreSQL. They apply Alembic head, then roll back each
test's transaction; do not supply a valuable local database. Non-local database
destinations and Railway environments are refused.

Applying migrations to Railway staging is a separate, explicitly authorized operation
(see [staging procedure](../docs/wo2-staging.md)); never run them against Railway from a
local machine.
