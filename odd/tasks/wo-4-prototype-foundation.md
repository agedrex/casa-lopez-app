# WO-4 — Prototype foundation

## Source of truth
- La Fábrica project: `casa-lopez-projecto1` (Casa Lopez - Projecto1)
- Stage: E1 — Descubrimiento y prototipo inicial
- Work Order: `WO-4` — Construir mockup inicial de frontend y backend para validar el flujo
- Feature: `FRD-COSTEO`
- Feature Blueprint: `BP-DESCUBRIMIENTO-COSTEO-PROTOTIPO-INICIAL`
- Supporting model Blueprint: `BP-MODELO-DATOS-INICIAL-COSTOS-PROVEEDORES`

## Goal
Create the smallest runnable Next.js frontend and FastAPI backend foundation and demonstrate an HTTP JSON connection between them, consistent with the WO-4 prototype scope.

## Explicit boundaries
- Demonstration/mockup only; no real quoting, production operations, or approved costing calculations.
- Do not invent or encode unvalidated formulas, units, cost rules, or definitive database schema.
- No PostgreSQL persistence: the blueprint says persistence is provisional and final schema is out of scope.
- Frontend identifies demo data as fictional and renders backend-provided sample resources.
- Next.js in `front/`; FastAPI dependency managed through `uv` in `backend/`.

## Tasks and outcomes
1. Initialize an isolated Git boundary and create this ODD record before source writes — complete; branch `feat/wo-4-prototype-foundation`.
2. Scaffold Next.js frontend and minimal FastAPI demo API — complete.
3. Connect the frontend to the API with configurable local API origin — complete; local origin defaults to `http://localhost:8000` and is configurable with `NEXT_PUBLIC_API_URL`.
4. Run applicable checks and inspect review authority — focused checks passed; native review inspect was blocked by the session Git authority/lifecycle error.

## Acceptance checks
- [x] Frontend and backend have documented local run commands (`README.md`).
- [x] FastAPI exposes `/api/health` and `/api/demo/resources`.
- [x] Next.js retrieves and renders API data with loading/error states.
- [x] CORS permits only the local frontend origin for requests.
- [x] No real costing or persistence behavior is implied.
- [x] `uv run --directory backend pytest -q`: 3 passed; one upstream Starlette/httpx deprecation warning.
- [x] `cd front && corepack pnpm run lint`: passed.
- [x] `cd front && corepack pnpm build`: passed.
- [x] Local API smoke check returned three demo resources.
- [ ] Browser-level visual / live frontend-to-API check not run (no browser verification tool available in this session).
- [ ] Native RDD review not run: `gentle_review inspect` returned `Session Git authority or lifecycle changed; cannot prepare its review repository.`

## Delegation note
The package-owned writer, incident scout, and verifier could not register the nested Git worktree because the session Git identity changed after initializing this repository. Native review inspection hit a corresponding authority error, and no native Agent tool was available. After the user's explicit instruction to proceed, implementation and checks were performed directly as a narrow fallback.

## Work-unit evidence
- Feature branch: `feat/wo-4-prototype-foundation`.
- Implementation commit: `4c23a1b` (`feat: scaffold Casa Lopez prototype stack`).
- Task-record evidence commit: `54d817f` (`docs: record WO-4 prototype verification`).
