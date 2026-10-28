# Grilla completa

## Objective

Show one live cost row per product at `/grilla`, using the existing `Catalogo` and `Costos_Variables` export data.

## Scope and constraints

- Base: `main` at `21430d4`; branch: `feat/grilla-completa`.
- Add one authenticated, read-only `GET /grilla` with optional text and category filters. Reuse `_catalogo` and `_costos_variables`; do not add monetary calculations, tables, or migrations.
- Show grouped, sortable, selectable columns on desktop; mobile product cards by default; download the visible rows and columns as CSV with API monetary strings unchanged.
- Keep the existing navigation entry under Consultas and Spanish UI text.
- Do not touch staging, Railway, or the unrelated `.codex/config.toml` change.
- The v4.1 workbook/Diccionario is not present in this checkout. SUPUESTO: the export tab headers are the available column contract.

## Delivery

- Strategy: single PR, as requested. Forecast: approximately 500 authored changed lines; keep backend and frontend in separate work-unit commits.
- Push `feat/grilla-completa`; provide PR title and body for the user to paste. Do not create or merge the PR.

## Tasks

- [x] G1 — Add the endpoint and focused endpoint test. Route: delegated direct; backend API and test require non-trivial edits. Check: AST and `git diff --check` passed; pytest pending because `uv` is absent and the local virtual environment points to a removed Python interpreter. Commit and RDD evidence below.
- [ ] G2 — Build responsive grid, cards, filters, sorting, column selection, and CSV. Route: delegated direct; page and client behavior require non-trivial edits. Check: lint, build, mobile layout where tooling permits, committed diff, RDD assessment.
- [ ] G3 — Push the branch and prepare the PR text. Route: inline repository state and delivery operations. Check: remote branch identity and final status.

## Progress

- Branch created from updated `main`.
- G1 response keeps the original export headers and row order, joins `Catalogo` and `Costos_Variables` by code, and serializes each cell as text. Optional text and exact category filters are case insensitive.
- G1 commit: pending.
- Engram recovery mirror pending because the runtime session identity is unavailable.

## Next step

Implement G1 with a read-only response contract that preserves export values.
