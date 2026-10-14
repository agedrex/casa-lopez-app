# WO-7 Auth CI and PostgreSQL 18.6

## Objective

Make the CI pipeline run focused Better Auth and admin tests, and strengthen the disposable PostgreSQL verification to use and assert PostgreSQL 18.6 while applying only the checked-in Better Auth schema.

## Problem

The frontend CI job linted and built the app without running the five focused auth/admin unit test files. The PostgreSQL verification used a floating major tag, created the checked-in schema when it was missing, and applied the generated SQL instead of the versioned artifact. It also did not verify that the disposable database remained free of the application costing schema and tables.

## Why

WO-7 requires repeatable auth verification against the pinned database version and guards against an auth-only workflow changing or introducing costing objects. A manually confirmed Railway staging snapshot is available (864 MB, 2026-10-14); restoration has not been tested. No production, Railway, Factory, or Engram operation is part of this work.

## Scope and constraints

- Edit `.github/workflows/ci.yml` and `scripts/wo7-ci-postgres.sh` only for implementation.
- Run no Docker, dependency installation, user creation, Alembic operation, Railway operation, or merge. A conventional commit and push to `feat/wo4-better-auth` are authorized after checks pass.
- Do not change auth implementation.
- Keep any pre-existing `.codex/config.toml` change untouched and uncommitted.
- Engram mirror is intentionally pending because the user prohibited Engram changes.

## Tasks

- [x] WO7-CI-1 Add the five focused auth/admin test files to frontend CI after frozen dependency installation.
- [x] WO7-CI-2 Pin the disposable database to PostgreSQL 18.6, assert and print its runtime version, and check for costing schemas/tables before and after auth verification.
- [x] WO7-CI-3 Require the versioned Better Auth SQL, compare it to generated Better Auth 1.7.7 SQL, and apply the versioned file.
- [x] WO7-CI-4 Run the authorized local syntax and focused test checks; record exact outcomes.

## Authorized scope

`.github/workflows/ci.yml`
`scripts/wo7-ci-postgres.sh`
`odd/tasks/wo7-auth-ci-postgres18.md`

## Acceptance criteria

- CI runs the five named test files using Node's test runner after `pnpm install --frozen-lockfile`.
- The disposable database runs `postgres:18.6` and fails unless `SHOW server_version` is exactly `18.6`.
- The harness checks for the `costos` schema and known costing tables before and after Better Auth checks.
- A missing versioned schema fails; a mismatch fails; only the versioned schema is applied.
- Existing localhost port binding, generated secrets, cleanup trap, and auth schema/integration checks remain in place.
- The snapshot availability is documented with restoration explicitly untested.

## Verification

- `bash -n scripts/wo7-ci-postgres.sh`
- Outcome: passed with exit code 0.
- `node --experimental-strip-types --test front/tests/auth-flows.test.ts front/tests/auth-internal.test.ts front/tests/auth-permissions.test.ts front/tests/admin-auth.test.ts front/tests/admin-status.test.ts`
- Outcome: passed, 22 tests, 0 failures. Node emitted `MODULE_TYPELESS_PACKAGE_JSON` performance warnings for the five test modules.
- Docker and pnpm are unavailable locally; do not install them or run the container harness.
- CI container execution, including image version and schema-generation/apply checks, remains pending in GitHub Actions.
- Read back all changed files after editing.

## Progress and next step

Implementation and authorized local checks are complete. Parent owns diff review, commit, and CI execution.

## Delivery

- Route: delegated direct, because implementation spans the workflow, harness, and recovery document.
- Forecast: approximately 90 authored lines, below the 400-line delivery threshold.
- Strategy: one reviewable work-unit commit on `feat/wo4-better-auth`; keep PR #4 in draft without merging.
- Rollback boundary: revert this document and the two CI changes to restore the prior workflow and harness.
- Runtime harness scenario: CI-only PostgreSQL container unavailable locally; staging snapshot restoration remains untested.
