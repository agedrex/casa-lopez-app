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

**Authentication is fail-closed.** Every route below depends on `require_user` (`auth.py`), which answers `401 {"detail": "No autenticado."}` when there is no valid Better Auth session (or no verifier is configured). The verifier calls `AUTH_VERIFY_URL` (the front's `get-session`) with the caller's cookie.

**Roles.** Reads (`GET`) are open to any signed-in user. Every `POST` also needs the role `admin` or `cotizador` (`ESCRITURA` in `api.py`, built with `require_role`); a `consulta` user gets `403 {"detail": "No tenés permiso para esta acción."}`. No session is still `401`, never `403`.

| Method and path | Roles | What it does |
|---|---|---|
| `GET /productos` | any signed-in | List: code, name, category, lifecycle state, cost today in ARS/USD (null if not computable) and warnings. `limit`, `offset`, `q` (every word must appear in the code, model, own name, leather or color) and `categoria` (exact name). The response is still a plain list. |
| `GET /productos/conteo?q=&categoria=` | any signed-in | `{"total": n}` for the same filters, so the UI can paginate without changing the list shape. |
| `GET /productos/{codigo}` | any signed-in | Sheet: recipe lines, cost today, saved quotes, `recotizar` flag, warnings. |
| `GET /modelos`, `/materiales`, `/parametros`, `/dolar` | any signed-in | Catalogs; the dollar is newest first. |
| `GET /personas` | any signed-in | People of the plantilla (`codigo`, `nombre`, `rol`, `activo`) for the "quién" and "persona" selects. |
| `GET /catalogos` | any signed-in | `{"colores": [...], "categorias": [...]}` names for the forms' selects. |
| `GET /precios?material=&a_fecha=` | any signed-in | Price history, newest first; `vigente` marks the price in force at `a_fecha` (default today). `variacion_pct` and `salto_grande` compare each price with the previous one of the same material, color and currency. |
| `GET /precios/chequeo?material=&color=&precio=&moneda=&vigente_desde=` | any signed-in | `{anterior, variacion_pct, salto_grande}` for a price about to be loaded. Saves nothing. A jump is more than `SALTO_PRECIO_PCT` (50 %, `SUPUESTO: validar`) and is only a warning: the load is never blocked. |
| `GET /costos-fijos?periodo=AAAA-MM` | any signed-in | Fixed costs of the month (default `PERIODO_VIGENTE`) with factory, store and grand `total` (pending amounts are counted in `pendientes`, never summed). |
| `GET /costos-fijos/periodos` | any signed-in | `{vigente, periodos}`: every period that has rows plus the current one, newest first. |
| `GET /talleres`, `GET /talleres/{codigo}` | any signed-in | Workshops with `ejemplo` (note starts with "Ejemplo"), `lotes`, `unidades`, `ultimo_lote` and `cobro_total_ars`; the detail adds its lots. |
| `GET /ordenes?estado=&donde=&taller=` | any signed-in | Lots newest first with products, units, quoted and charged totals, lot cost (materials of today + sewing), cost per unit and the sheet's control warnings. |
| `GET /ordenes/{codigo}` | any signed-in | A lot with its lines (sewing per unit = paid, else quoted; materials per unit today; cost per unit; line total) and its state history. |
| `GET /fabricacion/casa-vs-taller?hasta=AAAA-MM` | any signed-in | Last 12 months up to `hasta` (default this month), newest first: lots and units in house vs workshop, percent at workshops, what was paid and units per workshop. A lot counts in the month of its delivery date, else its shipping date; a lot without either counts nowhere. |
| `GET /productos/{codigo}/precios-talleres?mismo_tamano=true` | any signed-in | Latest price per workshop for the product (with the previous one and the change) and the latest price per (workshop, product) of similar products: same category and, by default, same size; `es_mismo_producto` marks the product itself. |
| `GET /calidad` | any signed-in | Data-quality findings grouped by topic, each `{severidad: alta|media|baja, entidad, mensaje, ruta}`, plus counts by severity. See "Data quality" below. |
| `POST /productos` | admin, cotizador | Create a product (`modelo`, `cuero`, `color`, `quien_lo_confecciona`, `fecha_de_alta`, `nombre_propio`, `es_kit`); the server assigns `PRD-nnnn`. |
| `POST /productos/{codigo}/extras` | admin, cotizador | Add an EXTRA recipe line (`material`, `color`, `consumo_neto_por_unidad`). |
| `POST /productos/{codigo}/componentes` | admin, cotizador | Add a component to a kit; kit cycles are refused. |
| `POST /productos/{codigo}/cotizaciones` | admin, cotizador | Save a quote `{tipo, fecha?}`: INICIAL uses `fecha_de_alta`, RECOTIZACION `fecha_de_recotizacion`, FINAL `fecha_de_cierre` (or the explicit date). Incomplete or dateless: 422 with the warnings; repeated (product, date, type): 409; never an UPDATE. |
| `POST /precios`, `/dolar`, `/costos-fijos`, `/ordenes` | admin, cotizador | Append-only loads. A price for the same material, color and date, or a dollar for the same date, type and source, is 409. A new lot also writes the first row of its state history. |
| `POST /ordenes/{codigo}/estado` | admin, cotizador | `{estado, fecha, quien?, fecha_de_entrega?}`: appends an `orden_estado` row and sets the lot's state. `CERRADA` needs a delivery date (the body's, else the lot's, else 422) and sets it. A closed lot never changes state again, and repeating the current state is refused: both 409. |
| `POST /ordenes/{codigo}/items` | admin, cotizador | Adds a product line `{producto, cantidad, taller_precio_cotizado_por_unidad_ars?, taller_precio_pagado_por_unidad_ars?}`; the server assigns `LIT-nnnn`. |
| `POST /ordenes/{codigo}/items/{item}/precios` | admin, cotizador | `{cotizado?, pagado?}` (at least one): records what the workshop quoted / charged per unit. The one in-place edit of lots (the workshop price arrives after sending). |
| `POST /talleres` | admin, cotizador | New workshop (`nombre`, `cuit?`, `telefono?`, `direccion?`, `contacto?`, `nota?`); the server assigns `TAL-nnnn`. A repeated name or CUIT is 409. |
| `POST /talleres/{codigo}/activo` | admin, cotizador | `{activo}`: deactivates or reactivates; nothing is deleted. |
| `POST /costos-fijos/{codigo}/monto` | admin, cotizador | `{monto_ars_del_mes}`: sets the amount of a row **only while it is empty** (409 otherwise): a correction is a new row. |

Errors: 401 not signed in, 403 role without write permission, 404 missing product, lot, workshop or expense, 409 already there, 422 refused (`detail` in Spanish).

### Lots, workshops, fixed costs and data quality (T5d)

Everything below is derived on every read from existing tables (no migration); the Google Sheet and the screens only display it. Rules come from the plantilla sheets `Lotes`, `Lote_Productos`, `Casa_vs_Taller`, `Precios_Talleres` and the `Control` columns.

- **Cost of a lot line** = (materials per unit today + sewing per unit) × quantity. Materials per unit = the product's cost today minus its sewing stage (`Costos_Variables!O − K`). Sewing per unit: in house 0; at a workshop what it charged (`pagado > 0`), else what it quoted, else nothing; a lot without a date has no sewing price. The lot cost is the sum of its lines and the cost per unit divides it by the units. A line whose product cannot be quoted today is left out of the sum and warned.
- **Warnings** (sheet order, all listed instead of only the first): lot — `Falta el taller` (EXTERNA), `Falta la fecha de envío`, `Sin productos`, `Falta la fecha de entrega` (CERRADA), `Hay productos con problemas`; line — `Falta la cantidad`, `Falta el precio del taller` (EXTERNA), `El lote no tiene fecha`, and `No se puede calcular el costo de hoy del producto` (added by the app).
- **State changes** append to `orden_estado` and set `orden_fabricacion.estado` in one transaction; rejected changes leave no history. `SUPUESTO: validar`: any state may follow any other (even going back) except after `CERRADA`; the first history row of a new lot is dated on its shipping date, else on the day it was loaded.
- **Price edits** (`.../precios`) update the line in place and **keep no audit trail**: `orden_estado` cannot hold prices and no table may be added. `SUPUESTO: validar`: add a price-history table if Casa López wants to see what the workshop asked first.
- **Workshops**: `ejemplo` is true when the note starts with "Ejemplo" (the three seeded ones). `SUPUESTO: validar`.
- **Fixed costs**: `POST .../monto` is a single `UPDATE ... WHERE monto IS NULL`, so two simultaneous requests cannot both win.

### Data quality (`GET /calidad`)

Groups (`clave`): `productos`, `recotizar`, `modelos_sin_validar`, `modelos`, `materiales`, `precios`, `lotes`, `talleres`, `gastos_fijos`, `parametros`. Each finding has a Spanish message and the front route where it is fixed (`ruta`). The product, lot and price rules are the ones already used elsewhere (quote warnings, `marca_recotizar`, `listar_precios` jumps, the lot warnings above); the report only gathers and classifies them, plus the date checks of `Productos!T` (`Nombre repetido`, `Falta la fecha de alta`, `La recotización es anterior al alta`, `El cierre es anterior al alta`, `PRODUCIDO` without `Falta la fecha de cierre`).

`SUPUESTO: validar` (the sheet has no severity column): **alta** = the product, lot or material cannot be quoted or closed (missing price, dollar, leather, workshop or delivery date); **media** = it can, but something is off (jumps, VAT included, repeated names, unconfirmed parameters of the "pendiente / propuesta" kind, pending or example workshops in use); **baja** = informative (models not validated, fictitious amounts, a parameter without a "confirmed" mark). Without any dollar on record a single `alta` finding asks for it instead of one per product. A price is "vigente" for the material check when it starts on or before today; non-quotable materials (lagarto, yacaré) show as `baja`. Models and parameters point at `/admin` until their screens exist (T5c).

The integration cases of the API (`tests/test_api_integration.py`) also need `TEST_DATABASE_URL`; each one runs inside a transaction that is rolled back, so the seeded database is left untouched.
