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

## DER v1 schema and migrations (WO 2)

The eleven phase-one models are in `src/backend/models.py`. All application tables
and Alembic's version table live in `costos`; Alembic excludes `public`, reserved
for Better Auth. Schema creation and seeds run only through the explicit revisions
`0001_esquema_costos` and `0002_semillas`, never during application startup.

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

The verification script checks revision, tables, seed counts, blocked exotic
materials, and GG. Optional write probes use savepoints inside one transaction
that always rolls back. It refuses Railway environments other than `staging`.
No credentials or connection diagnostics are printed.

`GET /db/estado` returns the current revision and application table count;
`GET /catalogo/etapas` returns the ordered public stage catalog. These endpoints
only read and expose no prices. Database failures return a generic 503.

Run tests from the repository root with `uv run --directory backend pytest -q`.
The fifteen PostgreSQL integration cases (thirteen constraints/seed checks and
two supplier downgrade regressions) skip unless `TEST_DATABASE_URL` is
explicitly supplied for a disposable local PostgreSQL. They apply Alembic head,
then roll back each test's transaction; do not supply a valuable local database.
Non-local database destinations and Railway environments are refused.

To verify a complete local migration cycle, run `downgrade base` only in that
disposable database and then `upgrade head` again. `downgrade -1` at head removes
only the catalog seeds, subject to foreign-key protections.

Local WO 2 evidence: 59 tests passed and 15 integration cases skipped; Python
compilation and the offline lock consistency check passed. Initially Alembic was
only resolved in the lock; dependency installation had not been authorized.
After explicit authorization, the existing uv tool synchronized declared packages
into the existing `backend/.venv`: Alembic 1.20.0 and Mako 1.4.3, with no new
Python or infrastructure installation. The same venv successfully ran actual
`alembic upgrade head --sql`, explicit-range offline downgrades, and `alembic heads`.
The generated SQL contains eleven domain tables, four indexes, and exact seeds;
the first statement creates `costos`, with no `public` operations. SQL generation
does not apply migrations. Live upgrade/check/round-trip and PostgreSQL integration
proof remain pending because no disposable local PostgreSQL was available.

Future staging application is a separate, explicitly authorized SSH operation
inside the backend container; do not run migrations against Railway from a local
machine. See [staging procedure](../docs/wo2-staging.md) and
[decisions and limitations](../docs/wo2-decisiones.md).
