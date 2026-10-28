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
- `lib/auth.ts`: Better Auth with the `admin` plugin and the roles `admin`, `cotizador` and `consulta` (`lib/permissions.ts`). Sign-up is disabled; an admin creates users. A `hooks.before` guard (`lib/user-guards.ts`, `lib/password.ts`) runs on `/admin/set-role`, `/admin/ban-user`, `/admin/create-user`, `/admin/set-user-password` and `/admin/remove-user`, for the server actions and for direct calls alike: nobody changes their own role or ban themselves, the last active admin stays, passwords must be strong, and nobody is deleted. The admin role is also stripped of the plugin's `delete`, `update`, `set-email` and impersonation permissions.
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

| `/voz` | `admin` and `cotizador` use it; `consulta` sees the explanation | Voice module. A text box (always there, editable), a push-to-talk "Hablar" button that uses the browser's `SpeechRecognition` / `webkitSpeechRecognition` with `lang = "es-AR"` (disabled with the reason where the browser has none, in an insecure context, or while the model is not configured), "Interpretar", and the proposal as an editable confirmation card ("Entendí esto… ¿Lo cargo?"): resolved fields are filled in, ambiguous ones are radio choices, missing ones are marked. Only "Confirmar y cargar" writes. Examples are UI copy. The privacy note says the text goes to the model provider and that the browser's dictation may send the audio to Google or Apple. |

## Writing from the screens

- Every write is a **server action** (`actions.ts` next to each page) that forwards the visitor's cookie to the API (`apiPost` in `lib/api.ts`). The browser never calls the API.
- Each action re-checks the role (`denyUnlessWriter` in `lib/write-guard.ts`); the forms are only rendered for `admin` and `cotizador` (`canWrite` in `lib/permissions.ts`), and the backend answers 403 to anyone else.
- Forms use `useActionForm` (`lib/use-action-form.ts`): a refused submission keeps what was typed, the result is announced through an `aria-live` region, and a successful one clears the fields.
- Amounts travel as text: `parseDecimalInput` only normalizes `1545,5` to `1545.5`; the frontend never adds, multiplies or compares money.
- Dynamic product rows (`app/(app)/fabricacion/product-rows.tsx`) are plain uncontrolled inputs that share a name per column; the action reads them as parallel lists and skips empty rows.
- The color select of the product form is empty until an admin creates colors in `/admin/catalogos` (the seeds carry none).

## Admin area (`/admin`, role `admin` only)

Each page calls `requireRole("admin")` and each server action starts with `denyUnlessAdmin()` (`lib/write-guard.ts`); the API checks the role a third time. Money and consumptions travel as text and are validated by the API; the frontend only shows them.

| Route | What it does |
|---|---|
| `/admin` | Cards with counts and a link to each section. |
| `/admin/usuarios` | List (email, name, role, active or deactivated, created) and, per user, change role, deactivate / activate, set a new password (all sessions of that user are closed; changing one's own password sends you to `/login`). New users get a password typed by the admin, with a strength check (at least 12 characters, three of four character types, not containing the email name). The controls of your own row are disabled. The password is read from the form, handed to Better Auth and dropped: it is never returned, logged or shown. |
| `/admin/parametros` | The parameters with value, unit, state and note. Editing asks twice: the second step shows the current and the new value and says that **the previous value is not saved** (the table has no history column; the API logs who changed what). Percentages are fractions between 0 and 1 (`0,05` = 5 %), the dollar and areas must be above 0, the period is `AAAA-MM`. Calculated parameters are not editable. |
| `/admin/modelos`, `/admin/modelos/[codigo]`, `/admin/modelos/nuevo` | Model list with search and category, size and validation filters (a plain GET form, the filters live in the URL); detail with the consumptions and their origin; "Marcar como validado" (a person confirms, never the app); "Nuevo modelo" (the server assigns `MOD-nnnn`); editing consumptions of an existing model shows a before / after table first, resets `validado` and only affects future quotes. |
| `/admin/catalogos` | Colors (`COL-nnnn`) and categories (`CAT-XXXX`, the first four letters of the name when free) with a create form each. Nothing is deleted or deactivated: those tables have no `activo` column. |
| `/admin/personas`, `/admin/impuestos` | People (create, deactivate / activate) and the taxes table (read only: whether VAT is a product cost is an open business decision). |
| `/admin/sync` | Google Sheet display copy (the Sheet only shows; nothing flows back). Shows whether the two backend variables are set (names only, never values), the last run kept in the backend's memory with rows per tab, a tab selector with the first 50 rows exactly as the Sheet would get them (a plain GET form, `?pestana=`), and two actions that each ask twice: "Simular (no escribe en Google)" and "Sincronizar ahora" (disabled, with the reason, while the variables are missing or a run is in progress). The page shows counts and text only; it never computes money. |

`components/confirm-form.tsx` is the two-step form used for parameters and consumptions: the first press shows what will change, the second one sends it, and editing a field in between takes the summary back.

## Voice module (`/voz`)

- `app/(app)/voz/actions.ts`: `interpretarVoz` (calls `POST /voz/interpretar`, returns the proposal) and `confirmarVoz`. The second one does **not** call a new endpoint: it re-checks the role (`denyUnlessWriter`) and runs the existing server actions (`createPrecio`, `createDolar`, `addExtra`, `savePrecios`, `setMonto`) with the fields of the card, so the person's session, the validations, the "big jump" confirmation and the 409 / 422 messages are exactly the ones of the regular screens. The `endpoint_destino` / `payload_propuesto` of the proposal are informational: the browser never sends them anywhere.
- `lib/use-dictation.ts` + `lib/voz.ts`: push-to-talk (`continuous = false`, `interimResults = true`, a click starts and a second click stops), support detected with `useSyncExternalStore` (unsupported on the server render, real answer after hydration), Spanish messages for each recognizer error. The microphone is released when the screen is left.
- Accessibility: the status of the dictation and of the interpretation is an `<output>` (live region), errors go to an `aria-live` region, focus moves to the card's heading when a proposal arrives, missing fields have text and `aria-invalid` (not only a color), everything works with the keyboard.
- The frontend never calculates money: it shows the decimal strings of the proposal and submits what the person confirmed. The model key lives in the backend only; `.env.example` mentions it as a comment.
- Support (MDN browser-compat-data, 2026-10-28): Chrome / Edge with `webkit` prefix from 33 and unprefixed from 139, Safari 14.1+ with the `webkit` prefix only, Firefox none. Not exercised in a real browser or with a real microphone in this task.

