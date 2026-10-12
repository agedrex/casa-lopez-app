# Railway staging deployment flow

## Goal

Configure Railway so pushes to `main` deploy the Casa Lopez frontend and backend to `staging`, while production remains unchanged until an explicit promotion. Do not create a database.

## Tasks and evidence

1. **Inspect Railway environments, services, and failures — done.** Project `casa-lopez` in Agedrex; staging `63b76478-71c4-4bc3-a67e-5bb24ecd231d`; production `eb50e642-d4e0-4e83-a08d-fdad62a2ee49`. Initial production builds failed because Railpack analyzed the monorepo root and found no app start script.
2. **Configure Railway service roots, launch settings, domains, variables, and deploy controls — done.** Both environments use backend root `/backend`, frontend root `/front`. Backend start command is `uv run fastapi run src/backend/main.py --host 0.0.0.0 --port $PORT`. Staging auto-deploy is enabled; production auto-deploy is disabled for both services. Each environment has Railway domains and its own API/CORS variables. No secrets or DB were added. Staging deploys on commit `c31ab1c81b77424ef11745ab7cbcaf1dec20b2c9` succeeded: backend `415bb29a-024b-4465-a0d5-195fd2ebd2aa`, frontend `b760ed16-0dcb-453c-b011-cf0fee63d355`.
3. **Make backend CORS configurable — done locally, not yet deployed.** Added `CORS_ALLOWED_ORIGINS`, preserving localhost and rejecting `*`; backend suite passes 5 tests. Frontend/API URL config is stored in Railway. Current GitHub `main` build predates this source change, so staging browser preflight still returns 400 until this branch change is delivered to `main` and auto-deployed.
4. **Deliver source change and verify functional staging, keeping production unchanged — in progress.** User explicitly authorized commit and push of `chore/railway-staging-deploy`; prepare a reviewable Conventional Commit with source, regression tests, and `backend/README.md`, then push the branch. Do not merge to `main` or deploy production. Verify branch push and production autodeploy state. Full browser/API preflight validation remains pending delivery to `main`.

## Functional checks observed

- Local checks: `uv run --directory backend pytest -q` (5 passed, one upstream Starlette deprecation warning); `cd front && corepack pnpm lint && corepack pnpm build` (passed).
- Live staging GET `https://backend-staging-566d.up.railway.app/api/health`: HTTP 200.
- Live staging frontend `https://frontend-staging-8dc6.up.railway.app/`: HTTP 200.
- Live staging CORS preflight from frontend origin: HTTP 400 before the local CORS source change was available to GitHub deployment. Therefore staging is deployed but cross-origin frontend/API integration is not yet functional.
- Verified Railway autodeploy status: staging true for both services; production false for both. Production received no deployment from this setup after disabling auto-deploy; its earlier failed initial deployment remains in history.

## Constraints

- Staging receives pushes to `main`; production requires explicit manual promotion.
- Keep env variables in Railway; no credentials in repo.
- Project ID `ffe35123-c0aa-4acf-92ff-62347a5daed3`.
- Services: backend `a5438e0d-03f4-4715-b1ae-07fcb5d8c8b0`; frontend `1bb7f66c-29a4-439f-861e-cc13eb2f40d9`.
