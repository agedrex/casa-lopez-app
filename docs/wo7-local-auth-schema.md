# WO-7 Stage 3: Better Auth schema verification

**Status (2026-10-14): Better Auth 1.7.7 schema and staging configuration are in place.** The four authentication tables were created and verified in `public`; the `costos` schema, its 11 tables, 38 seed rows, and revision `0002_semillas` remain intact. Seven Better Auth service variables were applied with deployment skipping enabled; no deployment was triggered. Staging login, logout, and permission behavior remain untested. PR [#4](https://github.com/agedrex/casa-lopez-app/pull/4) is a draft pending review and merge.

## CI verification flow

The isolated `auth-postgres` job in `.github/workflows/ci.yml` runs on GitHub's Ubuntu runner with `contents: read`. It installs the frontend from the frozen pnpm lockfile, then `scripts/wo7-ci-postgres.sh`:

1. Confirms Better Auth and its CLI are both pinned to 1.7.7.
2. Creates cryptographically random PostgreSQL and Better Auth secrets in the runner process environment.
3. Starts `postgres:18.6` in Docker, binding its randomly assigned host port only to `127.0.0.1`. It does not use `trust`, repository secrets, Railway, or La Fábrica.
4. Runs the pinned CLI against `front/lib/auth.cli.ts` to generate SQL from an empty database. The checked-in `front/db/better-auth-public.sql` must match the generated SQL byte for byte.
5. Applies the SQL with `psql` using `ON_ERROR_STOP`, runs `auth check schema`, and executes the static schema and real PostgreSQL integration tests.
6. Uploads only the generated SQL file from the runner's temporary directory as the `better-auth-public-schema` artifact, retained for seven days. The artifact contains schema DDL, not database rows or credentials. It remains available when later verification fails so the generated DDL can still be reviewed.

Secret-bearing commands run in one script with shell tracing disabled. The password is passed to Docker by environment variable name, not as an argument value. The script does not print connection URLs, cookies, tokens, or generated passwords. An exit trap removes the temporary container. The generated SQL remains in the runner's temporary directory so the following artifact step can upload it, including after verification fails.

## Integration coverage

Commit `340f111cad22857ef2221b907bc83e1cb5c0713a` passed [GitHub Actions run 38592816341](https://github.com/agedrex/casa-lopez-app/actions/runs/38592816341), including 22 focused auth/admin unit tests and the schema and real-database integration tests against PostgreSQL 18.6. Coverage includes objects constrained to schema `public`; a fresh PostgreSQL connection confirming persisted user, account, and session rows; email/password login; session retrieval and persistence; admin and user roles and permission checks; denial of browser sign-up and unauthorized role assignment; CSRF origin checks for logout; successful logout; and expired-session rejection. Test identities and passwords are generated in memory; response cookies and credentials are never logged.

The schema test verifies the four Better Auth tables, Admin plugin fields, relationships, and indexes. It rejects non-public schema objects, destructive DDL, and statements outside the expected table/index creation set.

## Session failure classification and renewal limitation

The internal verification endpoint returns `401` for missing, invalid, or expired sessions and recognized Better Auth authentication denials. Unexpected Better Auth, PostgreSQL, or session verification errors return a sanitized, uncached `503`. FastAPI preserves authentication failures as `401`, rejects verified non-admin users with `403`, and maps upstream service failures to a generic `503`. Next.js displays the existing administration-unavailable screen on session or permission service errors instead of redirecting to login. Every failure denies administrative access; exception messages and database details are not returned.

**Browser cookie renewal remains a known limitation.** Both Next.js admin checks and the internal endpoint call Better Auth's server-side `getSession` API for its parsed session value. Better Auth can extend the database session and generate renewal cookies during that call, but these paths do not propagate its `Set-Cookie` headers to the browser. The FastAPI-to-Next.js verification request also cannot renew the browser cookie. Continued use through these checks may therefore outlive the browser's original cookie expiry, causing the browser to lose its session and require another login even after a database renewal.

This change does not modify cookie renewal. **No temporal test was run** across the session refresh threshold or browser cookie expiry; the existing expired-session integration case proves rejection only. Before sustained use, add a browser-facing session refresh that delivers Better Auth's renewal cookies, then verify refresh and expiry over time in a browser.

## Staging application (2026-10-14)

The target was Railway project `casa-lopez`, environment `staging`, Postgres service `272f8917-f099-4b89-a085-cf9bc27b0ac1`. The approved SQL file had SHA-256 `77e72ce9e9f3fea2ab4d4380ff5f905ccdeb081dea31da6ac053822608725d1e` immediately before execution.

The read-only preflight confirmed PostgreSQL 18.6, no Better Auth tables in `public`, all 11 `costos` tables, 38 seed rows, and `costos.alembic_version = 0002_semillas`. Railway listed manual volume snapshot `bc916e3e-6d4a-4b50-a23c-56a01fed48e5`, created on 2026-10-14 with 864 MB referenced; it was available at the time of the check. **The snapshot's restoration has not been tested.**

The approved file was sent to staging Postgres `psql` with `ON_ERROR_STOP` and `--single-transaction`. The command exited `0`; the SQL was not reapplied. PostgreSQL reported that `public` already existed, then created the four tables and three explicit secondary indexes. Primary-key and unique indexes were created with their table constraints. No SQL was applied to `costos`.

## Read-only verification after application

| Check | Observed result |
| --- | --- |
| Authentication tables | Exactly `public.user`, `public.session`, `public.account`, and `public.verification`; all have zero rows. |
| Indexes | Nine expected indexes: four primary-key, two unique, and three explicit secondary indexes. |
| Key constraints | Eight expected: four primary keys, two unique constraints, and two foreign keys to `public.user`. PostgreSQL 18 also lists 24 `NOT NULL` constraints separately in `pg_constraint`; these are not extra key constraints. |
| Schema shape | Column names, types, and nullability match the approved Better Auth 1.7.7 SQL. |
| `costos` | The same 11 business tables; `costos.alembic_version = 0002_semillas`. Seed counts: `categoria` 3, `producto` 0, `etapa` 8, `material` 11, `proveedor` 2, `precio_material` 11, `tipo_cambio` 1, `parametro` 2, `cotizacion` 0, `cotizacion_linea` 0, `marca_calidad` 0. Total: 38. |
| Service state | Staging PostgreSQL responded to the postchecks; Railway listed Postgres, frontend, and backend deployments as `SUCCESS`. The manual snapshot remained listed and available. No deployment was triggered by this work. |

A supplemental **read-only** authentication row-count query initially failed because PowerShell passed quoted SQL incorrectly to `psql`, resulting in a database-name error. The query was resent through standard input inside a read-only transaction and confirmed zero rows in all four tables. This transport error did not affect the successful DDL transaction, and no schema application was repeated.

Seven Better Auth variables were applied to the existing Railway staging services with `skipDeploys: true`; existing variables were preserved:

| Service | Variable names |
| --- | --- |
| Frontend | `AUTH_DATABASE_URL`, `BETTER_AUTH_URL`, `BETTER_AUTH_SECRET`, `AUTH_INTERNAL_SECRET`, `AUTH_BACKEND_URL` |
| Backend | `AUTH_VERIFY_URL`, `AUTH_INTERNAL_SECRET` |

No deployment was triggered, and no production resources were changed. No users or administrators were created. The deployed application's login, logout, and permissions remain untested. PR [#4](https://github.com/agedrex/casa-lopez-app/pull/4) remains a draft pending review and merge.
