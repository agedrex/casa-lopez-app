# WO 2: DER v1 PostgreSQL schema

## Objective and authorization

Implement the 11 phase-one tables from `docs/der.md`, SQLAlchemy models,
Alembic schema and seed revisions, read-only endpoints, verification tools,
tests, and operating documentation. The backend currently connects to a database
but has no domain schema. Preserve Excel data, history, and Decimal precision.

Agustin approved Phase B and later authorized Phase C. The independent review
closed its two findings. Local work-unit commits are authorized on the existing
`feat/wo2-esquema-costos` branch. The approved delivery strategy is `single-pr`:
keep all component commits on this branch and prepare one PR to `main`. This is
an explicit exception to the advisory ~400 authored-line delivery budget. The
larger review/merge unit is accepted because each merge can trigger a Railway
staging deploy and Agustin wants rollout control. No Railway operation, remote
database access, staging migration, deployment, push, PR creation, or merge has
occurred as part of this documentation update. Use existing local tools; do not
install infrastructure software.

## Sources and scope

Authority: `docs/der.md` > `docs/der-borrador.sql` >
`docs/wo1-modelo-conceptual.md` > `AGENTS.md`.
These four files are user-owned and MUST remain byte-identical.
Implement phase one only. No cost engine, importer, frontend, authentication,
write endpoints, or automatic migration at startup/deploy.
Record source differences and backend-only future rules in
`docs/wo2-decisiones.md`. No credentials, connection hosts, or real URLs in
artifacts, logs, or terminal output.

## Work and acceptance criteria

- [x] T1: Implement 11 exact ORM tables, named constraints and indexes, with
  `costos` metadata, Decimal types, identities, and timezone-aware timestamps.
  Route: delegated; multi-file implementation and preparation trigger.
- [ ] T2: Add only Alembic as a production dependency, configure schema
  isolation, create `0001_esquema_costos` and `0002_semillas`, and verify offline
  SQL plus local upgrade/check/downgrade/re-upgrade when PostgreSQL is available.
  Route: delegated; migration code and focused execution trigger.
- [x] T3: Add read-only `/db/estado` and `/catalogo/etapas`, metadata and
  integration tests, and `backend.verificar_db` with environment guard and
  rollback-only constraint probes. Preserve existing backend behavior.
  Route: delegated; new logic across multiple files and execution trigger.
- [x] T4: Document decisions, local proof/limitations, and future staging SSH
  procedure; update backend README; independently verify and report approval two.
  Route: delegated; documentation preparation and verification trigger.

## Verification

Use the existing runner located by the worker (temporary `uv.exe` or backend
virtualenv). Relevant deterministic behavior tests must show observed RED before
GREEN where runnable; passive documentation needs structural readback.

- Run the existing backend tests and new model/router/script tests.
- Integration tests require an explicitly supplied disposable local
  `TEST_DATABASE_URL`; skip with a reason when unavailable. Never reuse an
  ambient `DATABASE_URL` for migration or testing.
- Generate offline SQL to a temporary file outside the repository, checking
  first-statement schema creation, 11 tables, exact constraints and seed counts.
- With disposable local PostgreSQL only: upgrade, current, check, downgrade,
  re-upgrade, seed counts, and preservation of a `public.user` sentinel table.
- Run independent verification and a parent structural spot check. Record every
  failed, skipped, or unavailable command as such; never infer success.
- Verify source-file hashes and diff whitespace; inspect changed files for
  secrets using redacted findings only.

## Delivery and review

Forecast: approximately 1,600–2,400 authored additions/deletions; generated lock
content excluded. The ~400-line delivery budget is advisory. Agustin explicitly
approved `single-pr`: retain all component commits on this branch and prepare
one PR to `main`. The accepted tradeoff is a larger review/merge unit; each
merge can trigger a Railway staging deploy, so one PR gives Agustin control over
rollout timing. The PR has not been created. Parent's approved read-only RDD
status query reports mode ON, decided by global configuration. Do not change the
switch or start native review while implementation is in progress; work-unit
review waits for the commit boundary.

## Progress and recovery

Recognition completed; user approved Phase B. Package: `backend/src/backend`.
Reuse URL normalizer and engine/session helpers in `database.py`.
Expected source differences include missing `created_at` on two SQL tables,
missing non-draft computed-cost CHECK, source-label differences, and carton
presentation data not specified in exact SQL seeds. Do not invent seed values.
The successful SSH command/cwd is not recorded; distinguish documented commands
from verified staging execution.

Engram mirror topic: `odd/wo2-esquema-costos/tasks`. Mirror pending: project
lookup fails and host session is unregistered. Local document is authoritative
for progress until memory becomes available.

Observed baseline: 27 tests passed. Observed RED: collection failed because
`backend.models` and `backend.verificar_db` did not yet exist. Observed GREEN:
54 tests passed, 13 integration cases skipped because `TEST_DATABASE_URL` is
absent and no disposable local PostgreSQL is available. Existing Starlette/httpx
deprecation warning remains non-failing. Python compileall passed.

T1 evidence: deterministic metadata and PostgreSQL DDL checks; frozen migration
declarations match ORM columns, identities, constraints, FKs, and four indexes.
T3 evidence: HTTP read routes, generic failures, environment refusal, one outer
rollback on success/failure, savepoint cleanup, and exact named-constraint
diagnostics are covered by deterministic tests. No business engine was added.

T2 implementation exists: Alembic env/config, schema revision, exact seven seed
INSERT statements, and dependency lock. `uv add --offline alembic` failed due
to missing cache. Existing uv then resolved the lock successfully (68 packages,
Alembic 1.20.0, Mako 1.4.3) without installing packages. Offline lock check passed.
At the initial Phase B closure, Alembic was not installed in the existing venv;
`python -m alembic upgrade head --sql` failed with `No module named alembic`.
At that point, upgrade/current/check/downgrade/
re-upgrade, live counts, and `public.user` preservation remain unrun. Autogenerate
was unavailable, so 0001 was written as explicit frozen operations and compared
structurally. T2 remained partially verified; the later local synchronization
section records the completed actual offline SQL generation.

SQL reference: `C:/Users/agus-/AppData/Local/Temp/wo2-esquema-referencia.sql`.
Compiled from frozen declarations without the Alembic runtime, not applied and
not represented as Alembic-generated SQL. First SQL statement creates `costos`;
11 domain tables, four indexes, seven seed INSERTs, no public operations.

T4 documentation is written in `docs/wo2-decisiones.md`, `docs/wo2-staging.md`,
and backend README. Staging result section is empty. Final SHA256 values for
all four protected files equal the initial values. Final suite rerun: 54 passed,
13 skipped, one existing deprecation warning; compileall passed. Tracked diff
whitespace check passed; independent verification follows. Git reports existing
pytest-cache access and lockfile line-ending warnings, without failed checks.
No commit, staging operation, or deployment has occurred.

Independent verification initially returned CHANGES_REQUESTED: supplier seed
downgrade selected non-unique display names, and seed validation checked only
exotic flags/GG rather than exact contents. One bounded correction round fixed
both. The downgrade now captures two exact seed price and supplier IDs through
their existing relationships inside one PostgreSQL DO statement, before any
deletion; missing/ambiguous identities refuse safely. Unrelated supplier IDs or
other providers' prices are not deleted. Existing dependent data can prevent
material removal through FKs, rolling back the operation.

Verification now compares the entire seven-table initial catalog by natural
keys and exact source VALUES/defaults without printing monetary values. RED:
five new regressions failed. Focused GREEN: 21 passed. Final command:
`backend/.venv/Scripts/python.exe -m pytest -q -rs backend/tests --basetemp
C:/Users/agus-/AppData/Local/Temp/casa-lopez-wo2-correction -p no:cacheprovider`.
Observed result: 59 passed, 15 skipped, one existing warning. The original 13
integration cases plus two supplier downgrade regressions require disposable
local PostgreSQL. Compileall passed, and original SHA256 hashes still match.

The upgrade SQL reference is unchanged. Additional frozen downgrade reference:
`C:/Users/agus-/AppData/Local/Temp/wo2-semillas-downgrade-referencia.sql`.
It contains the guarded DO SQL, was not emitted by the Alembic runtime, and was
not applied. Live DO/migration verification remains unavailable. T4 documentation
records findings, correction evidence, and the safe refusal assumption.
Native assessment is high/unassessable due to untracked inventory; do not treat
it as passive. No native lifecycle has started. Follow the native contract at
the authorized work-unit commit boundary without changing the RDD switch.

Independent targeted verification closed both correction findings with no
remaining blocker in that scope and independently observed 59 passed, 15 skipped,
and one existing warning. The verifier confirmed the outer transaction begins
before inspection and rolls back in finally. Parent final whitespace check,
branch identity, and all four protected SHA256 comparisons passed. T4 is complete;
T2 remains partially verified because live PostgreSQL proof is unavailable.
No native lifecycle or commit was performed. Engram mirror remains pending.

## Review inventory

Modified implementation files (4):

- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/src/backend/main.py`
- `backend/README.md`

New implementation and tracking files (17):

- `backend/alembic.ini`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_esquema_costos.py`
- `backend/migrations/versions/0002_semillas.py`
- `backend/src/backend/models.py`
- `backend/src/backend/routers.py`
- `backend/src/backend/db_verification.py`
- `backend/src/backend/verificar_db.py`
- `backend/tests/test_models.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_integration.py`
- `backend/tests/test_read_routes.py`
- `backend/tests/test_verificar_db.py`
- `docs/wo2-decisiones.md`
- `docs/wo2-staging.md`
- `odd/tasks/wo2-esquema-costos.md`

The four user-owned source documents are preserved inputs, not implementation
changes. Native assessment remains high/unassessable due to untracked inventory.

Current verification: 59 tests passed and 15 were skipped because disposable
local PostgreSQL is unavailable. Alembic generated offline SQL successfully;
live PostgreSQL migration and integration validation remain pending. Next,
complete the authorized work-unit commits on this branch, then prepare one PR to
`main` under the approved `single-pr` strategy. Do not apply migrations in
Railway or deploy.

## Authorized local dependency synchronization and actual offline SQL

At the initial review Agustin withheld commits, but authorized installation only
of declared backend dependencies into the existing venv. The later Phase C
authorization covers local commits. Before synchronization: existing uv 0.13.0,
Python 3.13.16 at `backend/.venv/Scripts/python.exe`, and Alembic module absent.
The prior failure was caused by lock resolution without package synchronization,
which was previously outside authorization; no model or migration defect caused it.

`uv sync --frozen --offline --no-python-downloads --directory backend` failed
because package wheels were not cached. The normal sync hit sandbox socket error
10013; the exact command rerun with runtime approval succeeded. It prepared two
packages, replaced the editable backend, and installed three entries: Alembic
1.20.0, Mako 1.4.3, and local backend 0.1.0. No new Python, global packages,
Postgres, Docker, or infrastructure was installed. Alembic's module location is
now confirmed inside the unchanged existing venv; project/lock were frozen.

Actual Alembic commands used that venv Python and a process-only synthetic URL,
without printing/storing connection values or contacting any database:

- `upgrade head --sql`: exit 0, `C:/Users/agus-/AppData/Local/Temp/wo2-esquema.sql`.
- `downgrade 0002_semillas:0001_esquema_costos --sql`: exit 0,
  `C:/Users/agus-/AppData/Local/Temp/wo2-semillas-downgrade.sql`.
- `downgrade 0002_semillas:base --sql`: exit 0,
  `C:/Users/agus-/AppData/Local/Temp/wo2-downgrade-base.sql`.
- `heads`: exit 0, `0002_semillas (head)`.

Actual upgrade SQL inspection passed: first statement creates costos, 11 domain
tables plus version table, four indexes, eleven ALWAYS identities, eleven
timezone-aware created_at columns, every named constraint, and seven exact seed
INSERTs with row counts 8/11/2/11/1/2/3. No public operations or DROP SCHEMA.
Offline downgrade renders the guarded supplier/price ID capture and reverse
domain-table removals. Earlier reference artifacts remain explicitly historical.

Post-sync suite command used `--basetemp
C:/Users/agus-/AppData/Local/Temp/casa-lopez-wo2-alembic-installed` with cacheprovider
disabled and DB variables cleared: 59 passed, 15 skipped, one existing warning.
Compileall, offline frozen lock check, and protected four SHA256 comparisons passed.
T2 is still partial solely for unavailable disposable local PostgreSQL: live
upgrade/current/check/downgrade/re-upgrade, actual counts, public sentinel, and
15 integration cases remain pending. Staging result section stays empty.

Local PostgreSQL verification remains pending if a disposable instance becomes
available. Agustin has authorized Phase C, subject to the recorded delivery
strategy and native review contract. No Railway operation or deployment occurred.
Engram mirror remains pending.
