# PostgreSQL connection foundation

## Objective

Prepare the existing FastAPI backend to use the staging PostgreSQL service through DATABASE_URL, without creating tables or changing data.

## Problem and scope

The backend currently exposes fixed demo responses and has no database configuration, driver, engine, or sessions. Add SQLAlchemy 2 and psycopg 3, safe configuration, connection/session lifecycle, an internal SELECT 1 command, deterministic tests, and usage documentation.

No Railway operations, production access, table creation, migrations, push, merge, or deployment are authorized. A staging connection check requires separate user authorization before execution. Never print credentials or store real connection URLs.

## Work unit

- [x] PG-01: Implement and verify the connection foundation, then create a local Conventional Commit with code, tests, dependencies, and documentation.

Route: delegated direct. Trigger: multiple non-trivial source/test files, dependency tooling, and reading that prepares a write. One writer owns the implementation; independent verification follows if native assessment is high or unavailable.

Acceptance: PostgreSQL URL aliases use psycopg; invalid/missing configuration fails without secret exposure; engines and request sessions are closed correctly; SELECT 1 is available only through an internal command; no new diagnostic route or schema exists; existing demo behavior remains usable without DATABASE_URL.

Verification: observe meaningful RED before implementation; run focused database/command tests, the full backend pytest suite, uv lock --check, and git diff --check. Tests use synthetic URLs and mocks without remote connections. The real staging SELECT 1 check remains pending user authorization.

## Delivery and progress

Branch: feat/der-postgres-demo. Starting boundary: aa5dd17e4fc1ed84044bc87134e51616b86361d6.

Forecast: approximately 350 authored changed lines, generated lockfile excluded. Strategy: ask-on-risk; no push or PR creation authorized. Keep a single coherent unit unless implementation reveals a meaningful split.

Pre-existing user change: .codex/config.toml; do not include or modify it.

Tooling: uv is absent and the detected concrete Python is below the required version. Use temporary tooling/cache directories rather than modifying global configuration. Native review mode is on, verified with a read-only escalated command; candidate consent remains separate.

Engram mirror: pending; the host session registration hook currently blocks writes. Local task progress is authoritative until persistence is available.

Implementation and verification are complete. Authored implementation diff: 310 lines excluding the generated uv.lock (138 changed lines), this task file, and the unrelated user configuration. The source changes remain a single coherent work unit.

Observed RED: focused pytest collection failed because SQLAlchemy and backend.db_check were absent before implementation.

Observed GREEN: focused database/check tests passed (22); full backend suite passed (27), including an independent offline rerun. uv lock --check passed and the parent independently reran it offline (66 packages). git diff --check passed. Known non-failing warnings: Starlette/httpx deprecation and restricted pytest cache writes.

Independent verification found no severe candidate-caused defects. No PostgreSQL network check was run; real staging SELECT 1 remains pending explicit authorization.

Temporary tools: uv and Python 3.13.16 under the task-specific Temp directory; backend/.venv contains local dependencies. UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR, and UV_PYTHON_BIN_DIR point into Temp. The initial Python install warned about executable links in the default user bin directory before UV_PYTHON_BIN_DIR was set; no external cleanup was attempted.

Implementation commit: bc45b67 (feat(backend): configure PostgreSQL connections and sessions). Committed change: 495 lines total, including 138 generated lockfile lines; approximately 357 authored lines including this task document. No push, merge, or deployment occurred.

Native committed-only assessment against aa5dd17e4fc1ed84044bc87134e51616b86361d6: medium (configuration_change in backend/pyproject.toml), review_due=false, review_due_reason=under_budget. The implementation remains pending in the review slice; no native review or approval is claimed. The unrelated configuration was excluded from the commit and assessment.

Next step: when explicitly authorized, run the documented internal SELECT 1 command in Railway staging. Actual PostgreSQL connectivity remains unverified. DER tables, models, and migrations are future work outside this unit.
