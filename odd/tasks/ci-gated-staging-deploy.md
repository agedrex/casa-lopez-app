# CI-gated staging deployment

## Goal

Keep direct pushes to `main` issue/PR-free, run backend and frontend checks automatically, and make Railway staging wait for successful GitHub Actions check suites. Production remains manual and isolated.

## Tasks

1. Add a least-privilege GitHub Actions workflow that runs backend pytest and frontend lint/build on pushes (including `main`). **In progress** — main run `38274466064` passed but reported deprecated Node 20 runtimes in action versions. Updating to Node 24-compatible releases before final verification; workflow keeps `contents: read` and runs on all branches.
2. Enable Railway Wait for CI (`checkSuites`) on the two staging deployment triggers only; preserve production auto-deploy disabled. **Done** — staging triggers `2b1426fd-5415-4cfc-adc2-462b9c6f48eb` and `56a13035-6da1-4b08-af5a-5b1e55cbfc26` have `checkSuites:true` and one valid check suite each; production auto-deploy remains false.
3. Verify workflow status, gated staging deployment, production isolation, and production readiness facts. **Pending final rerun** — earlier main run `38268945883` passed and verified both staging deployments waited for CI and then succeeded; live staging frontend/API and CORS checks passed. Production remained untouched; its current domains return HTTP 404.
4. Document the deploy gate and remaining steps to launch the demo in production. **Done in README** — production remains unlaunched pending explicit manual deployment and smoke test.

## Completion evidence

- Implementation commits: `5b4b0f9` (`ci(deploy): gate staging rollout on checks`) and `2817767` (direct push to `main`).
- GitHub Actions main run `38268945883` succeeded both jobs; follow-up run `38274466064` also succeeded but emitted Node 20 deprecation annotations, prompting the action-version refresh.
- Railway staging deployments for commit `2817767`: backend `91661ef6-563b-4c17-b97f-4ad280072a3c`; frontend `d65abbc7-8186-403b-8ffd-3f72d1d9070c`; both `SUCCESS`.
- Production has no healthy deployment. Manual promotion and production smoke checks are still required; no database is needed for this demo.

## Known state

- GitHub default branch `main`, commit `3a8c553`; direct push policy; main unprotected and no rulesets, so this adds deploy gating without requiring PRs.
- Railway project `ffe35123-c0aa-4acf-92ff-62347a5daed3`.
- Staging environment `63b76478-71c4-4bc3-a67e-5bb24ecd231d`; production `eb50e642-d4e0-4e83-a08d-fdad62a2ee49`.
- Staging service trigger IDs: backend `2b1426fd-5415-4cfc-adc2-462b9c6f48eb`; frontend `56a13035-6da1-4b08-af5a-5b1e55cbfc26`. Both have `checkSuites:true` and `validCheckSuites:1`.
- Production auto-deploy is disabled for both services. Neither service currently has a production deployment trigger; the only production deployments are initial failures from the unconfigured repository root.
- Production settings already include roots, start command (backend), Railway domains, and per-environment frontend/API/CORS variable names. Both current production domains return HTTP 404; production has no healthy deployment yet.
- No database is needed for the fictional demo data.

## Safety constraints

- Do not enable Railway production auto-deploy or deploy to production as part of this work.
- Preserve direct-to-main pushes; no issue, PR, or branch-protection rule that requires PRs.
- Railway Wait for CI gates deployment, not the commit itself: a failing commit may land on `main`, but should not deploy to staging. Document this tradeoff.
