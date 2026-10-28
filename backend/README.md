# Casa Lopez demo API

Run the local API from the repository root:

```sh
uv run --directory backend fastapi dev src/backend/main.py --host 127.0.0.1 --port 8000
```

The public routes (`/api/health`, `/api/demo/*`, `/db/estado`, `/catalogo/etapas`) expose health, fictional demonstration resources and catalog metadata. The costing endpoints below are real data and require a signed-in user.

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

## Costing API (T3b)

`servicios.py` loads rows and delegates every rule to the pure `costeo.py` / `receta.py`; `api.py` only validates input and calls it. The recipe, the quotes and all calculations live in the app; the Google Sheet only displays. Calculated values (name, category, totals, costs) are never accepted from the client: request bodies reject unknown fields with 422. Money is `Decimal` in the service and a string in JSON.

**Authentication is fail-closed.** Every route below depends on `require_user` (`auth.py`), which answers `401 {"detail": "No autenticado."}` while no verifier is configured, so today all of them are closed. The Better Auth check is task T4: implement it in `auth.get_verifier` (marked `# T4:`) or inject it with `app.dependency_overrides[get_verifier]`. The older public routes are unchanged.

| Method and path | What it does |
|---|---|
| `GET /productos` | List: code, name, category, lifecycle state, cost today in ARS/USD (null if not computable) and warnings. `limit`, `offset`. |
| `GET /productos/{codigo}` | Sheet: recipe lines, cost today, saved quotes, `recotizar` flag, warnings. |
| `GET /modelos`, `/materiales`, `/parametros`, `/talleres`, `/dolar` | Catalogs; the dollar is newest first. |
| `GET /precios?material=&a_fecha=` | Price history, newest first; `vigente` marks the price in force at `a_fecha` (default today). |
| `GET /costos-fijos?periodo=AAAA-MM` | Fixed costs of the month (default `PERIODO_VIGENTE`) with factory and store totals. |
| `POST /productos` | Create a product (`modelo`, `cuero`, `color`, `quien_lo_confecciona`, `fecha_de_alta`, `nombre_propio`, `es_kit`); the server assigns `PRD-nnnn`. |
| `POST /productos/{codigo}/extras` | Add an EXTRA recipe line (`material`, `color`, `consumo_neto_por_unidad`). |
| `POST /productos/{codigo}/componentes` | Add a component to a kit; kit cycles are refused. |
| `POST /productos/{codigo}/cotizaciones` | Save a quote `{tipo, fecha?}`: INICIAL uses `fecha_de_alta`, RECOTIZACION `fecha_de_recotizacion`, FINAL `fecha_de_cierre` (or the explicit date). Incomplete or dateless: 422 with the warnings; repeated (product, date, type): 409; never an UPDATE. |
| `POST /precios`, `/dolar`, `/costos-fijos`, `/ordenes` | Append-only loads. A price for the same material, color and date, or a dollar for the same date, type and source, is 409. |

Errors: 401 not signed in, 404 missing product, 409 already there, 422 refused (`detail` in Spanish). Lot status history (`orden_estado`) is not written yet.

The integration cases of the API (`tests/test_api_integration.py`) also need `TEST_DATABASE_URL`; each one runs inside a transaction that is rolled back, so the seeded database is left untouched.
