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

**Roles.** Reads (`GET`) are open to any signed-in user. Every `POST` also needs the role `admin` or `cotizador` (`ESCRITURA` in `api.py`, built with `require_role`); a `consulta` user gets `403 {"detail": "No tenés permiso para esta acción."}`. The admin area (parameters, people, colors, categories and the consumptions of a model) needs the role `admin` (`ADMINISTRACION` / `SoloAdmin`): a `cotizador` gets 403 there too. No session is still `401`, never `403`.

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
| `GET /modelos?q=&categoria=&validado=&tamano=&limit=&offset=` | any signed-in | Models in sheet order. `q`: every word in the code or name (wildcards are plain text); `categoria`: exact name; `validado`: `true` / `false`; `tamano`: `CHICO` / `MEDIANO` / `GRANDE`. |
| `GET /modelos/{codigo}` | any signed-in | A model with its consumptions, origin, note, reference to the old Excel row and `productos` (how many products use it). |
| `GET /colores`, `GET /categorias` | any signed-in | `[{codigo, nombre, nota}]` by name (`/catalogos` keeps returning only the names). |
| `GET /impuestos` | any signed-in | Taxes with `alicuota`, `base` and `es_costo_del_producto`. Read only: there is no write endpoint. |
| `POST /parametros/{codigo}` | **admin** | `{valor or valor_texto, fuente_estado: Pendiente\|Propuesta\|Confirmado, nota?}`. Overwrites in place (see below). 422 for calculated parameters (`DOLAR_VIGENTE`, `FECHA_DOLAR_VIGENTE`, or a row whose state starts with "Calculado") and for out-of-range values; 404 unknown code. |
| `POST /personas`, `POST /personas/{codigo}/activo` | **admin** | New person `{nombre, rol, vinculo, nota?}` (`PER-nnnn`; a repeated name, ignoring case, is 409) and `{activo}`: deactivates or reactivates, nothing is deleted. |
| `POST /colores`, `POST /categorias` | **admin** | `{nombre, nota?}`. The name is unique ignoring case (409); the server assigns `COL-nnnn` or the category code (see below). |
| `POST /modelos` | admin, cotizador | New model (name, `categoria` name, `tamano?`, forro `MAT-FO..`, all consumptions, `origen_de_los_consumos`, `nota?`). Server code `MOD-nnnn`; always created `validado = false`; a repeated name is 409. Consumptions are non-negative with the model's precision (`NUMERIC(12,6)` m² / juegos / horas, `NUMERIC(14,4)` USD and ARS). |
| `POST /modelos/{codigo}/validado` | admin, cotizador | `{validado}`: a person confirms (or withdraws) the numbers. |
| `POST /modelos/{codigo}/consumos` | **admin** | Replaces the consumptions (every field must be sent, `null` = missing data, so a partial body is 422), sets `validado = false` and logs the previous values. Saved quotes are snapshots and keep their numbers; every later quote of the model's products uses the new ones. |

Errors: 401 not signed in, 403 role without write permission (admin area: any role but `admin`), 404 missing product, lot, workshop or expense, 409 already there, 422 refused (`detail` in Spanish).

### Admin area (T5c)

No migrations or model changes: everything uses the existing tables.

- **Parameters change in place and keep no history.** `parametro` has no history column and no table may be added, so the previous value is not stored. Each change is logged (`parameter, user id, old -> new, state`) and `fuente_estado` always holds `Pendiente`, `Propuesta` or `Confirmado`, optionally followed by `: note`; the data-quality report still reads that leading word. `SUPUESTO: validar`: add a history table if Casa López wants to see old values. The services read the parameters on every quote, so the next quote uses the new value; saved quotes do not change.
- **Ranges** (`SUPUESTO: validar`, the sheet states none), by the parameter's unit: `%` is a fraction from 0 to 1 (`0.05` = 5 %); `ARS/USD` and `m2` must be above 0; `AAAA-MM` is a text `YYYY-MM`; any other unit is not editable. Values keep `NUMERIC(14,4)`; more decimals are 422.
- **Category codes** (`SUPUESTO: validar`): 15 of the 16 seeded codes are `CAT-` plus the first four letters of the name without accents (`CAT-PORT`, `CAT-RINO`); a new one follows that when the code is free and the name has four letters, else `CAT-nnnn`. Colors are `COL-nnnn` (the plantilla's sequence). Neither table has an `activo` column, so nothing can be deactivated.
- **Models**: `validado` is a flag a person flips; editing consumptions is a separate admin-only endpoint that always resets it, so a validated model cannot silently change. The previous values are logged, not stored (same limitation as parameters). The data-quality findings of models point at `/admin/modelos` and those of parameters at `/admin/parametros`.
- Audit lines go to the `uvicorn.error` logger (uvicorn sets it to INFO; the application's root logger would drop them). They carry the opaque user id and the values, never a secret.

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

`SUPUESTO: validar` (the sheet has no severity column): **alta** = the product, lot or material cannot be quoted or closed (missing price, dollar, leather, workshop or delivery date); **media** = it can, but something is off (jumps, VAT included, repeated names, unconfirmed parameters of the "pendiente / propuesta" kind, pending or example workshops in use); **baja** = informative (models not validated, fictitious amounts, a parameter without a "confirmed" mark). Without any dollar on record a single `alta` finding asks for it instead of one per product. A price is "vigente" for the material check when it starts on or before today; non-quotable materials (lagarto, yacaré) show as `baja`. Models point at `/admin/modelos` and parameters at `/admin/parametros`.

The integration cases of the API (`tests/test_api_integration.py`) also need `TEST_DATABASE_URL`; each one runs inside a transaction that is rolled back, so the seeded database is left untouched.

## Google Sheet display copy (T6)

**The Sheet is display only.** The app calculates everything (costing stays in `costeo.py` / `receta.py`, reached through `servicios.py`); it pushes plain values to a Google Sheet and **nothing is ever read back**. Editing the Sheet changes nothing in the app and is overwritten on the next sync. No formulas, no migrations, no new tables. Runbook for the people who set it up (Spanish): [`docs/sheets-sync.md`](../docs/sheets-sync.md).

Design: the FastAPI backend writes through the Google Sheets API v4 with a service account. No n8n in the data path (n8n may later just call `POST /sync/sheets`).

| Endpoint | Who | What it does |
|---|---|---|
| `POST /sync/sheets` | **admin** | Body `{"simular": bool}` (optional; unknown fields are 422). Builds every tab and, unless it is a dry run, replaces their values in the Sheet. `simular` left out = dry run while the Google variables are missing, real push once they are set. Returns `{simulacion, configurado, iniciado, finalizado, duracion_ms, total_filas, pestanas: [{nombre, filas}]}`. **409** while another run is in progress (process-level lock), **422** for a real push without the variables (the message names them), **502** with a fixed Spanish message when Google fails (never Google's own text or the credential). |
| `GET /sync/sheets/estado` | any signed-in | `{configurado, variables, faltantes, pestanas, en_curso, ultima}`: yes/no and the variable **names**, never the values or the Sheet id; `ultima` is the summary of the last run (also failed ones, with `ok` and `error`). |
| `GET /sync/sheets/vista/{pestana}` | **admin** | The first 50 rows of one tab as JSON (every cell as text, money as an exact decimal string) for the preview screen; 404 for a name that is not ours. Reads only, never calls Google. |

### Environment variables (read only from the environment)

| Variable | What it is |
|---|---|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | The id in the Sheet's URL (`/d/<id>/edit`). |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The **content** of the service account's JSON key (never a path). Never logged, never in a repr, never returned by an endpoint. |

Without both, `configurado` is false and only dry runs work. `.env.example` files carry no values for these.

### Tabs (the fixed list the app owns)

`Info` (generated-at timestamp, app version, row counts and the note "Vista generada por la app. No editar: se pisa en cada sincronización."), `Catalogo`, `Costos_Variables`, `Cotizaciones`, `Productos`, `Modelos`, `Precios`, `Dolar`, `Lotes`, `Lote_Productos`, `Costos_Fijos` (each row repeats the factory / store totals of its period), `Talleres`, `Parametros`, `Materiales`, `Calidad` (the findings of `GET /calidad`).

Headers are the column names of the plantilla v4.1 (sheet `Diccionario`). `Catalogo` and `Costos_Variables` are views the plantilla does not sync; here the app computes them with the existing services (`servicios.productos_costeados`), without reimplementing any cost. Cells: exact `Decimal` (no `float` inside the app), dates `YYYY-MM-DD`, booleans `SI` / `NO`, `None` as an empty string, text starting with `= + - @` (or tab / CR) gets a leading `'`, and a cell is cut at 50,000 characters.

### What the client does (`sheets_client.py`)

Per run: one read of the existing tabs, one `spreadsheets.batchUpdate` (`addSheet` for a missing tab, `updateSheetProperties` to resize and freeze the header row of the others; at least 2 rows, because Sheets refuses to freeze every row), one `values:batchClear` of the whole tabs and one `values:batchUpdate` with `valueInputOption: RAW`. It **never touches a tab outside the fixed list and never deletes a tab**. Retries with exponential backoff (1 s doubling, max 30 s, `Retry-After` honoured up to 60 s, 5 attempts) on 429 / 500 / 502 / 503 / 504 and network errors; other errors are mapped to a fixed Spanish message. Authentication uses `google-auth` (JWT signing and token exchange) with an `httpx` transport; scope `https://www.googleapis.com/auth/spreadsheets` only. Tests play Google with `httpx.MockTransport`; nothing in the suite calls a real Google endpoint.

### SUPUESTOS (`validar`)

- The only place where a `Decimal` becomes a JSON number is the final write to Google (written from its exact digits, never through `float`); the Sheet is display only, so Google's own double precision is accepted there.
- The last-run summary and the lock live in memory: lost on restart, and each replica has its own. No table was added.
- Clear and write are two calls: a failure between them leaves the app's tabs empty until the next sync.
- "Today" for the price in force and the quality report is the Argentine date (fixed UTC-3, no daylight saving).
- The tabs hold CUIT / phone / address of workshops: anyone with access to the Sheet sees them.
- `POST /sync/sheets` has no service-token path yet; an n8n schedule would need one (future work).

## Voice module (T7)

**The model interprets, it never calculates or decides, and a person confirms.** Runbook for the people who set it up (Spanish): [`docs/voz.md`](../docs/voz.md). No migration and no table: nothing is stored, the per-user limit lives in memory.

| Endpoint | Who | What it does |
|---|---|---|
| `POST /voz/interpretar` | **admin**, **cotizador** | Body `{"texto": "..."}` (1 to 500 characters; unknown fields and longer text are 422). Asks the model to EXTRACT an action and raw mentions, resolves them against the database and answers a **proposal**: `{accion, resumen, campos_resueltos, candidatos, faltantes, avisos, endpoint_destino, payload_propuesto}`. Writes nothing. **503** `El módulo de voz no está configurado: falta la clave del modelo.` without the key, **429** (with `Retry-After`) over 20 requests a minute per user, **504** / **502** with a fixed Spanish message when the model times out or fails (never the provider's text). |
| `GET /voz/estado` | any signed-in | `{configurado, acciones, max_caracteres, limite_por_minuto}`: yes or no, never the key, the model or the address. |

Layout: `voz_llm.py` is the model client behind the `VozLLM` protocol (`interpretar(texto, hoy) -> Interpretacion`); `voz.py` is the resolver (`proponer`), the rate limiter and `FuenteVoz` / `FuenteSQL` (read-only access to the catalog through `servicios`); the two routes in `api.py` only wire them.

- **Closed schema.** `Interpretacion` has the action (`cargar_precio`, `cargar_dolar`, `agregar_extra`, `registrar_precio_taller`, `cargar_monto_gasto`, `desconocida`) and bounded text fields (`material`, `color`, `producto`, `lote`, `taller`, `concepto`, `numero`, `moneda`, `tipo_dolar`, `fecha`, `periodo`, `cotizado_o_pagado`). The model returns it through ONE strict tool (`extraer_orden`, `tool_choice` forced); the answer is re-validated with Pydantic and anything invalid becomes `desconocida`. The user's sentence travels alone in the user turn between `<comando>` tags (the delimiter cannot be forged from inside it); the system prompt says to treat it as data and ignore instructions in it.
- **Resolver.** Mentions are matched without accents or case, by whole words (a prefix counts), preferring a code written in the sentence and then an exact name; `1.480,50`, `26,5` or `lote 3` are read deterministically (words like "mil" are refused, not interpreted). One match resolves, several give up to five `candidatos` (`codigo` is the value to send; for a color, its name), none is a missing field. Non-quotable materials are never proposed or offered. A future date is refused unless the sentence writes it out; a missing date is today (Argentine day), said in `avisos`. Price and dollar jumps over 50 % reuse `servicios.chequear_precio` / `variacion_de_precio` and only add a warning.
- **`payload_propuesto` is exactly a valid body** for `endpoint_destino`: it is built with the same models the write endpoints use (`PrecioIn`, `DolarIn`, `ExtraIn`, `PreciosItemIn`, `MontoIn`), and it is `null` (like `endpoint_destino`) while anything is missing or ambiguous. Every rule that protects the data stays in the existing endpoints (409, 422, append-only).
- **Model client.** `POST {base}/v1/messages` over `httpx`, no SDK, headers `x-api-key` and `anthropic-version: 2023-06-01`. Default model `claude-haiku-5-5`. `temperature` is **not** sent: the current docs ask to omit it on the 5.x models. 15 s in total, `max_tokens` 512, one retry on 429 / 5xx (`Retry-After` honoured up to 5 s); a 400 that rejects the forced tool (Opus / Sonnet 5.5) retries once with `tool_choice: auto`. Logs hold the action, latency, outcome class and the sentence LENGTH, never the text, the prompt or the key.

### Environment variables (read only from the environment)

| Variable | What it is |
|---|---|
| `ANTHROPIC_API_KEY` | Required to enable the module. Never logged, never in a repr, never returned. |
| `VOZ_LLM_MODEL` | Optional. Default `claude-haiku-5-5`. |
| `VOZ_LLM_BASE_URL` | Optional, for tests (a fake server). Default `https://api.anthropic.com`; anything that is not an `http(s)` URL is ignored. |

### SUPUESTOS (`validar`)

- 20 requests per minute per user, counted per process (lost on restart, one count per replica).
- A dot followed by exactly three digits (`1.480`) is read as thousands (es-AR) and warned.
- A price uses the material's consumption unit; no VAT split (same as the prices screen).
- Fixed costs are pesos only: dollars are not converted.
- No history of interpreted commands is kept (it would need storage).

