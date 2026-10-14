# WO-7 Stage 3: Better Auth schema verification

**Status: pending.** The schema has not been generated or applied to PostgreSQL. Stage 3 is complete only after CI produces the SQL artifact, the artifact is reviewed, and a later approved change versions the reviewed SQL.

## CI verification flow

The isolated `auth-postgres` job in `.github/workflows/ci.yml` runs on GitHub's Ubuntu runner with `contents: read`. It installs the frontend from the frozen pnpm lockfile, then `scripts/wo7-ci-postgres.sh`:

1. Confirms Better Auth and its CLI are both pinned to 1.7.7.
2. Creates cryptographically random PostgreSQL and Better Auth secrets in the runner process environment.
3. Starts `postgres:17` in Docker, binding its randomly assigned host port only to `127.0.0.1`. It does not use `trust`, repository secrets, Railway, or La Fábrica.
4. Runs the pinned CLI against `front/lib/auth.cli.ts` to generate SQL from an empty database. If a versioned SQL file exists, CI requires a byte-for-byte match. While it is absent, CI copies the generated file into the runner workspace only.
5. Applies the SQL with `psql` using `ON_ERROR_STOP`, runs `auth check schema`, and executes the static schema and real PostgreSQL integration tests.
6. Uploads only the generated SQL file from the runner's temporary directory as the `better-auth-public-schema` artifact, retained for seven days. The artifact contains schema DDL, not database rows or credentials. It remains available when later verification fails so the generated DDL can still be reviewed.

Secret-bearing commands run in one script with shell tracing disabled. The password is passed to Docker by environment variable name, not as an argument value. The script does not print connection URLs, cookies, tokens, or generated passwords. An exit trap removes the temporary container. The generated SQL remains in the runner's temporary directory so the following artifact step can upload it, including after verification fails.

## Integration coverage

The real database test bootstraps temporary admin and user identities through Better Auth's server API, since browser sign-up remains disabled. It checks email/password sign-in, session retrieval and persistence, user/account/session rows in a fresh PostgreSQL connection, admin permission behavior, denial of browser account creation and role assignment, logout, and expired-session rejection. Test identities and passwords are generated in memory; response cookies and credentials are never logged.

The schema test verifies the four Better Auth tables, Admin plugin fields, relationships, and indexes. It rejects non-public schema objects, destructive DDL, and statements outside the expected table/index creation set.

## Local status and next step

This preparation did not install PostgreSQL on Windows and did not run the PostgreSQL integration test locally. `front/db/better-auth-public.sql` remains absent until CI generates it, so the schema test cannot pass locally yet. No placeholder SQL is checked in.

After CI completes, review the artifact's generated DDL and verification result. Version the reviewed SQL only in a separately approved change. Any staging database application is a later, separate gate and requires explicit authorization; this workflow does not connect to staging, production, or Railway.
