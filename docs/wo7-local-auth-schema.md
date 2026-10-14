# WO-7 Stage 3: Better Auth schema verification

**Status: technically verified in ephemeral PostgreSQL CI.** Commit `7089cbcc9b040d8d26ee371e6fb19f8af3bcc929` versions the generated schema at `front/db/better-auth-public.sql`. GitHub Actions run [38502734966](https://github.com/agedrex/casa-lopez-app/actions/runs/38502734966) completed successfully. This verifies the schema and auth behavior in an isolated CI database; applying it to staging and verifying the staging application remain pending and require explicit authorization.

## CI verification flow

The isolated `auth-postgres` job in `.github/workflows/ci.yml` runs on GitHub's Ubuntu runner with `contents: read`. It installs the frontend from the frozen pnpm lockfile, then `scripts/wo7-ci-postgres.sh`:

1. Confirms Better Auth and its CLI are both pinned to 1.7.7.
2. Creates cryptographically random PostgreSQL and Better Auth secrets in the runner process environment.
3. Starts `postgres:17` in Docker, binding its randomly assigned host port only to `127.0.0.1`. It does not use `trust`, repository secrets, Railway, or La Fábrica.
4. Runs the pinned CLI against `front/lib/auth.cli.ts` to generate SQL from an empty database. The checked-in `front/db/better-auth-public.sql` must match the generated SQL byte for byte.
5. Applies the SQL with `psql` using `ON_ERROR_STOP`, runs `auth check schema`, and executes the static schema and real PostgreSQL integration tests.
6. Uploads only the generated SQL file from the runner's temporary directory as the `better-auth-public-schema` artifact, retained for seven days. The artifact contains schema DDL, not database rows or credentials. It remains available when later verification fails so the generated DDL can still be reviewed.

Secret-bearing commands run in one script with shell tracing disabled. The password is passed to Docker by environment variable name, not as an argument value. The script does not print connection URLs, cookies, tokens, or generated passwords. An exit trap removes the temporary container. The generated SQL remains in the runner's temporary directory so the following artifact step can upload it, including after verification fails.

## Integration coverage

The successful run applied the versioned SQL to temporary PostgreSQL 17 and passed the schema and real-database integration tests. Coverage includes objects constrained to schema `public`; a fresh PostgreSQL connection confirming persisted user, account, and session rows; email/password login; session retrieval and persistence; admin and user roles and permission checks; denial of browser sign-up and unauthorized role assignment; CSRF origin checks for logout; successful logout; and expired-session rejection. Test identities and passwords are generated in memory; response cookies and credentials are never logged.

The schema test verifies the four Better Auth tables, Admin plugin fields, relationships, and indexes. It rejects non-public schema objects, destructive DDL, and statements outside the expected table/index creation set.

## Staging status and next step

The CI run does not connect to staging, production, Railway, or La Fábrica. Applying the versioned schema to staging and verifying the deployed application are still pending; both require explicit authorization. No staging change is claimed here.

## Stage 6 staging gates

Stage 6 remains pending. Before any staging schema action, confirm a strictly read-only revision check using `SELECT version_num FROM costos.alembic_version`; do not use `alembic current`, because `env.py` may create the schema and commit. Also confirm a secure, reproducible admin-account creation procedure: the admin CLI may be absent from the deployed frontend image, so do not install tools or create accounts ad hoc. No staging action is complete or implied by the CI evidence above.

### Read-only Railway staging preflight (2026-10-14)

The `casa-lopez` project has distinct `staging` and `production` environments. Explicitly targeted staging metadata showed successful current deployments for frontend, backend, and Postgres, with the Postgres volume ready. Railway SSH reached the staging Postgres service and found `psql`. No deployment or configuration was changed.

Queries executed in a `READ ONLY` transaction confirmed all 11 expected tables in `costos`, `costos.alembic_version = 0002_semillas`, and the absence of the four Better Auth tables in `public`. The `public` schema exists; the connected database role has database-connect and public-schema usage/create privileges. No SQL was applied and no staging rows, tables, or settings were modified.

The staging server reports PostgreSQL 18.6, while the successful CI integration tests used PostgreSQL 17. Railway showed no volume backup, backup schedule, or PITR for the staging Postgres volume. An external recovery mechanism was not established. **Do not apply the authentication SQL until a recoverable backup or equivalent restoration path is confirmed and separately authorized.**

The current frontend SSH shell did not expose `node`, `corepack`, or `pnpm`; this does not establish what the future WO-7 deployment image will contain. The pinned Better Auth CLI is a frontend development dependency, so the administrator bootstrap procedure still needs an image-specific, secure verification before account creation. No account was created.

PR [#4](https://github.com/agedrex/casa-lopez-app/pull/4) remains a draft. Its frontend CI job runs lint and build, but does not invoke the focused auth/admin unit tests. Add a dedicated test step before merge and verify its result. The separate `auth-postgres` job already covers schema and real-database integration; a later successful run [38505564021](https://github.com/agedrex/casa-lopez-app/actions/runs/38505564021) also passed. Staging authentication, authorization, and administrator login remain untested.
