# Railway staging deployment flow

## Goal

Configure Railway so pushes to `main` deploy the Casa Lopez frontend and backend to `staging`, while production remains unchanged until an explicit promotion. Do not create a database.

## Tasks and evidence

1. **Inspect Railway environments, services, and failures — done.** Project `casa-lopez` in Agedrex; staging `63b76478-71c4-4bc3-a67e-5bb24ecd231d`; production `eb50e642-d4e0-4e83-a08d-fdad62a2ee49`. Initial production builds failed because Railpack analyzed the monorepo root and found no app start script.
2. **Configure Railway service roots, launch settings, domains, variables, and deploy controls — done.** Both environments use backend root `/backend`, frontend root `/front`. Backend start command is `uv run fastapi run src/backend/main.py --host 0.0.0.0 --port $PORT`. Staging auto-deploy is enabled; production auto-deploy is disabled for both services. Each environment has Railway domains and its own API/CORS variables. No secrets or DB were added. Staging deploys on commit `c31ab1c81b77424ef11745ab7cbcaf1dec20b2c9` succeeded: backend `415bb29a-024b-4465-a0d5-195fd2ebd2aa`, frontend `b760ed16-0dcb-453c-b011-cf0fee63d355`.
3. **Make backend CORS configurable — done.** Added `CORS_ALLOWED_ORIGINS`, preserving localhost and rejecting `*`; backend suite passes 5 tests. Documented the variable in `backend/README.md`.
4. **Publish source fix to review branch — done.** User authorized commit and push of `chore/railway-staging-deploy`. Code/test/doc commit `2a62219` (`fix(backend): configure explicit CORS origins`); task evidence commit `9f305cb` (`docs(odd): record railway deployment evidence`). Branch pushed to `origin/chore/railway-staging-deploy`. PR URL: https://github.com/agedrex/casa-lopez-app/pull/new/chore/railway-staging-deploy. No PR was created and nothing was merged to `main`.
5. **Merge to main and verify functional staging, keeping production unchanged — pending.** Staging's currently deployed `main` still predates the CORS change. After the PR is merged (user-owned), Railway should auto-deploy staging; verify frontend-origin preflight succeeds and production autodeploy remains disabled. Do not merge or deploy production without explicit user decision.

## Functional checks observed

- Local checks: `uv run --directory backend pytest -q` (5 passed, one upstream Starlette deprecation warning); `cd front && corepack pnpm lint && corepack pnpm build` (passed).
- Independent verifier confirmed exact configured origin is allowed, localhost remains allowed, unrelated origins are denied, and `*` is ignored (5 tests passed in its isolated copy).
- Live staging GET `https://backend-staging-566d.up.railway.app/api/health`: HTTP 200.
- Live staging frontend `https://frontend-staging-8dc6.up.railway.app/`: HTTP 200.
- Live staging CORS preflight from frontend origin: HTTP 400 before the local CORS source change reached GitHub main. Functional frontend/API integration is therefore pending PR merge and staging redeploy.
- Verified Railway autodeploy status: staging true for both services; production false for both. Production received no deployment from this setup after disabling auto-deploy; its earlier failed initial deployment remains in history.

## Constraints

- Staging receives pushes to `main`; production requires explicit manual promotion.
- Keep env variables in Railway; no credentials in repo.
- Project ID `ffe35123-c0aa-4acf-92ff-62347a5daed3`.
- Services: backend `a5438e0d-03f4-4715-b1ae-07fcb5d8c8b0`; frontend `1bb7f66c-29a4-439f-861e-cc13eb2f40d9`.
