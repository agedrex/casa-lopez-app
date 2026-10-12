# CI-gated staging deployment

## Goal

Keep direct pushes to `main` issue/PR-free, run backend and frontend checks automatically, and make Railway staging wait for successful GitHub Actions check suites. Production remains manual and isolated.

## Tasks

1. Add a least-privilege GitHub Actions workflow that runs backend pytest and frontend lint/build on pushes (including `main`). **Done** — `.github/workflows/ci.yml` uses Node 24-compatible action releases, `contents: read`, and push/workflow_dispatch triggers. Local `actionlint` passes; latest main run `38275920150` passed both jobs.
2. Enable Railway Wait for CI (`checkSuites`) on the two staging deployment triggers only; preserve production auto-deploy disabled. **Done** — staging triggers `2b1426fd-5415-4cfc-adc2-462b9c6f48eb` and `56a13035-6da1-4b08-af5a-5b1e55cbfc26` have `checkSuites:true` and one valid check suite each; production auto-deploy remains false.
3. Verify workflow status, gated staging deployment, production isolation, and production readiness facts. **Done** — latest main run `38275920150` passed; both staging deployments for commit `b01d626` waited for CI and then succeeded. Staging frontend/API returned HTTP 200 and CORS preflight allowed the staging origin. Production remained untouched; its current domains return HTTP 404.
4. Document the deploy gate and remaining steps to launch the demo in production. **Done in README** — production remains unlaunched pending explicit manual deployment and smoke test.

## Completion evidence

- Implementation commits: `5b4b0f9` (`ci(deploy): gate staging rollout on checks`), `2817767` (direct push to `main`), and `b01d626` (Node 24-compatible action runtimes).
- GitHub Actions main run `38275920150` passed both jobs without the previous Node 20 runtime warnings; GitHub displayed only an informational notice about a planned `ubuntu-latest` migration to Ubuntu 26.
- Railway staging deployments for commit `b01d626`: backend `100172d1-1b1b-495e-9048-1a0bd20e0258`; frontend `bdf59bc5-821f-4c89-b287-70d80f9d18b5`; both `SUCCESS`.
- Production has no healthy deployment. Manual promotion and production smoke checks are still required; no database is needed for this demo.

## Known state

- GitHub default branch `main`, commit `b01d626`; direct push policy; main unprotected and no rulesets, so this adds deploy gating without requiring PRs.
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
