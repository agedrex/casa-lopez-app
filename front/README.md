# Casa López · frontend

Next.js 16 (App Router, Cache Components), React 19, Tailwind CSS 4, Better Auth. UI copy is in Spanish; code and comments are in English.

```sh
corepack pnpm install
cp .env.example .env.local   # fill in DATABASE_URL and BETTER_AUTH_SECRET
corepack pnpm auth:migrate   # Better Auth tables in schema `public` (never Alembic)
SEED_USER_PASSWORD='choose-a-password' corepack pnpm seed:user
corepack pnpm dev
corepack pnpm lint && corepack pnpm build
```

Environment variables, roles and the backend side (`AUTH_VERIFY_URL`) are documented in the [root README](../README.md#authentication-and-environment-variables).

## How it fits together

- `proxy.ts` (Next 16's replacement for `middleware`): no session cookie sends the visitor to `/login`; `/admin` also checks the role against the database. `/login` and `/api/auth/*` are public.
- `lib/auth.ts`: Better Auth with the `admin` plugin and the roles `admin`, `cotizador` and `consulta` (`lib/permissions.ts`). Sign-up is disabled; an admin creates users.
- `lib/session.ts`: server-side session checks used by pages (the proxy check is only optimistic).
- `lib/api.ts`: server-only client for the costing API. It forwards the visitor's `cookie` header and redirects to `/login` on a 401. The browser never calls the API.
- `lib/format.ts`: display formatting of decimal strings. The frontend never calculates money.
- Design tokens (palette, fonts, radius) are in `app/globals.css`, taken from casalopez.com.ar.

## Routes

| Route | Who | What it does |
|---|---|---|
| `/dolar` | everyone sees; `admin` and `cotizador` load | Rate history (latest row highlighted) and a form (date, pesos per dollar, type, source `MANUAL`, note). Append-only: no edit or delete. A repeated date and type shows the API's 409 as "Ya hay un dólar cargado para esa fecha y tipo." |
| `/materiales` | everyone sees; `admin` and `cotizador` load | Materials grouped by stage with unit and quotable flag, each with its price history (the "vigente" one marked). "Cargar precio nuevo": the unit is forced to the material's consumption unit. Non-quotable materials (lagarto, yacaré) show "Bloqueado: falta definir unidad" and take no price. A price more than 50 % away from the previous one asks for a confirmation ("Cargar igual"); the percentage comes from the API. |
| `/productos` | everyone | List with search (`q`, code or name words) and category filter; both survive pagination (`?q=&categoria=&pagina=`). The total comes from `GET /productos/conteo`. |
| `/productos/nuevo` | `admin`, `cotizador` | New product: model (type to search the list), quotable leather, optional color, who makes it, date, own name, kit flag. On success it redirects to the sheet. |
| `/productos/[codigo]` | everyone sees; `admin` and `cotizador` act | Cost today, recipe, saved quotes, a side by side comparison (inicial / recotización / final / hoy) and the actions: save a quote, add an extra, add a kit component (kits only). A quote that cannot be saved shows the API's list of missing data; a repeated one shows the 409. |

| `/fabricacion` | everyone sees; `admin` and `cotizador` create | Lots with filters (state, in house / workshop, workshop; plain GET form, the filters live in the URL), totals and warnings from the API, and below it the house vs workshop summary of the last 12 months (bars are CSS widths from the API's percentage; no chart library). |
| `/fabricacion/nuevo` | `admin`, `cotizador` | New lot: where, workshop (or person), shipping date and a dynamic list of products with quantity and quoted price. Redirects to the lot. |
| `/fabricacion/[codigo]` | everyone sees; `admin` and `cotizador` act | Summary, lines with sewing / materials / cost per unit, state timeline, per-line form to record the workshop's quoted and paid prices, state-change form (closing asks for the delivery date; a closed lot hides the form) and "add a product". |
| `/talleres`, `/talleres/[codigo]`, `/talleres/nuevo` | everyone sees; `admin` and `cotizador` write | Workshop list and detail (lots, units, total charged), create form and activate / deactivate. The seeded ones carry a "Taller de ejemplo" badge (the API reads it from their note). |
| `/costos-fijos` | everyone sees; `admin` and `cotizador` load | Period selector (`?periodo=AAAA-MM`, default the current period), factory / store / grand totals from the API, rows grouped by category with "Pendiente de monto" and "Ficticio" badges, an inline amount form for pending rows and a form to add an expense. |
| `/calidad` | everyone | Counts by severity (each links to its filter), filters by severity, topic and text, and the findings grouped by topic with a link to where each one is fixed (a group shows its first 50 unless filtered to that topic). |

## Writing from the screens

- Every write is a **server action** (`actions.ts` next to each page) that forwards the visitor's cookie to the API (`apiPost` in `lib/api.ts`). The browser never calls the API.
- Each action re-checks the role (`denyUnlessWriter` in `lib/write-guard.ts`); the forms are only rendered for `admin` and `cotizador` (`canWrite` in `lib/permissions.ts`), and the backend answers 403 to anyone else.
- Forms use `useActionForm` (`lib/use-action-form.ts`): a refused submission keeps what was typed, the result is announced through an `aria-live` region, and a successful one clears the fields.
- Amounts travel as text: `parseDecimalInput` only normalizes `1545,5` to `1545.5`; the frontend never adds, multiplies or compares money.
- Dynamic product rows (`app/(app)/fabricacion/product-rows.tsx`) are plain uncontrolled inputs that share a name per column; the action reads them as parallel lists and skips empty rows.
- The color selects are empty today: the seeds carry no colors yet, and no screen creates them.
