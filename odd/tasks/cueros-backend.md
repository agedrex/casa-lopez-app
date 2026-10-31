# Leather inventory backend

## Objective
Implement the purchase, cut, remainder, stock summary, piece history, and availability loop using the existing DER v3 leather tables.

## Scope and constraints
- Branch `feat/cueros-backend` from updated `main`.
- `docs/der-v3.md` and `backend/src/backend/models.py` define the persisted fields.
- No migrations or model changes; no deletions. Use Decimal for money and square metres.
- Push only the feature branch. Prepare PR text without `gh`, merging, or pushing main.

## Tasks
- [x] T1 (inline, user prohibited helper agents): Implement leather service rules and the six requested endpoints. Response and permission contracts reviewed; CI pending.
- [x] T2 (inline): Cover purchase waste, cutting, remainder, summaries, availability, pricing, and role gates with focused tests. CI pending.
- [ ] T3 (inline): Run `uv run --directory backend pytest -q` or CI fallback, review the diff, commit, push, and prepare PR text.

## Acceptance criteria
- New purchases append a natural-waste movement of 10%; existing stock does not.
- Cutting uses an existing order item, cannot exceed stock or reopen a closed piece, and changes ENTERA to EN_USO.
- Irrecoverable remainder writes the remaining waste and closes the piece; reusable remainder becomes RETAZO.
- Summary and availability use movement-derived stock, Decimal values, price and dollar conversion, and sorted piece options.
- Current write endpoints remain closed to corte; only cut and remainder accept it.

## Verification
- `uv run --directory backend pytest -q` if available; otherwise GitHub CI on push.
- Review staged diff and preserve unrelated local changes.

## Progress
- `main` fast-forwarded to `f001efa`; feature branch created.
- `uv run --directory backend pytest -q` could not start: `uv` is not installed. CI fallback pending.
- Added `backend/src/backend/cueros.py`, six API routes, pure calculation tests, role-gate tests, and PostgreSQL integration tests (run only with `TEST_DATABASE_URL`).
- Existing exotic leathers remain eligible for inventory entry because the requested rule covers every material in CUERO; price fallback requires a compatible m² price.
- A purchase price requires its currency so the waste cost is not silently misinterpreted.
- Engram mirror pending while the host session remains unregistered.
- Forecast exceeds 400 authored lines because the requested workflow includes persistence, six endpoints, and tests; one coherent backend PR matches the requested branch and PR handoff.
