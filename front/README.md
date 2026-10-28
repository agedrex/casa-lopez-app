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
