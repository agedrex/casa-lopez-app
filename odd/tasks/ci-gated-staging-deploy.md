# CI-gated staging deployment

## Goal

Keep direct pushes to `main` issue/PR-free, run backend and frontend checks automatically, and make Railway staging wait for successful GitHub Actions check suites. Production remains manual and isolated.

## Tasks

1. Add a least-privilege GitHub Actions workflow that runs backend pytest and frontend lint/build on pushes (including `main`). **Done locally** — `.github/workflows/ci.yml`; backend 5/5 tests, frontend lint/build, and `actionlint` pass. Workflow uses `contents: read` and runs on all branches so it can be tested before `main`.
2. Enable Railway Wait for CI (`checkSuites`) on the two staging deployment triggers only; preserve production auto-deploy disabled. **In progress** — GraphQL schema confirms `deploymentTriggerUpdate`; staging triggers identified and currently false.
3. Verify workflow status, gated staging deployment, production isolation, and production readiness facts. **Pending**
4. Document the deploy gate and remaining steps to launch the demo in production. **Pending**

## Known state

- GitHub default branch `main`, commit `984324d`; direct push policy; main unprotected, no rulesets, no Actions workflows before this change.
- Railway project `ffe35123-c0aa-4acf-92ff-62347a5daed3`.
- Staging environment `63b76478-71c4-4bc3-a67e-5bb24ecd231d`; production `eb50e642-d4e0-4e83-a08d-fdad62a2ee49`.
- Staging service trigger IDs: backend `2b1426fd-5415-4cfc-adc2-462b9c6f48eb`; frontend `56a13035-6da1-4b08-af5a-5b1e55cbfc26`. Both currently have `checkSuites:false`.
- Production auto-deploy is disabled for both services. Neither service currently has a production deployment trigger; the only production deployments are initial failures from the unconfigured repository root.
- Production settings already include roots, start command (backend), Railway domains, and per-environment frontend/API/CORS variable names. Production has no healthy deployment yet.
- No database is needed for the fictional demo data.

## Safety constraints

- Do not enable Railway production auto-deploy or deploy to production as part of this work.
- Preserve direct-to-main pushes; no issue, PR, or branch-protection rule that requires PRs.
- Railway Wait for CI gates deployment, not the commit itself: a failing commit may land on `main`, but should not deploy to staging. Document this tradeoff.
