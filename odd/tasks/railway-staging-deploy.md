# Railway staging deployment flow

## Goal

Avoid mandatory issue creation and PR ceremony for this repo's small deployment path. Push tested changes to `main`; Railway auto-deploys them to staging. Production stays manual. No database.

## Current work

1. **Inspect GitHub rules — done.** The issue-first PR requirement came from the generic Gentle AI `branch-pr` skill, not evidence in this repository. GitHub API reports `main` is not protected, there are no repository rulesets, and no Actions workflows are configured. This supports the requested no-issue path: direct push to `main` without a PR.
2. **Configure Railway — done.** Project `casa-lopez` (`ffe35123-c0aa-4acf-92ff-62347a5daed3`); staging `63b76478-71c4-4bc3-a67e-5bb24ecd231d`; production `eb50e642-d4e0-4e83-a08d-fdad62a2ee49`. Service roots are `/backend` and `/front`; backend start command `uv run fastapi run src/backend/main.py --host 0.0.0.0 --port $PORT`. Staging auto-deploy is on and production auto-deploy is off for both services. Variables and Railway domains are environment-specific. No DB or secrets added.
3. **Add configurable CORS — done.** `CORS_ALLOWED_ORIGINS` preserves localhost and rejects wildcard entries; exact origin allowlist is documented in `backend/README.md` and tested. Commits `2a62219`, `9f305cb`, and `e9f3af1` are on `chore/railway-staging-deploy`.
4. **Document and use the direct-main workflow — in progress.** Document it in root README, then fast-forward push the tested branch to `main` (no PR and no issue). This follows the user's instruction to avoid the issue/PR bottleneck. Direct pushes result in staging deployment only.
5. **Verify deployment boundaries and functionality — pending.** Confirm staging CORS preflight and both apps after the push; confirm production auto-deploy is still disabled and no production deployment occurred.

## Verified evidence

- `main` has no branch protection (GitHub API 404: Branch not protected); repo rulesets list is empty; no Actions workflows configured.
- Local checks before this workflow update: backend `pytest -q` 5 passed (one upstream Starlette deprecation warning); frontend lint and production build passed.
- Previous staging deploy of old main commit `c31ab1c81b77424ef11745ab7cbcaf1dec20b2c9` succeeded: backend `415bb29a-024b-4465-a0d5-195fd2ebd2aa`, frontend `b760ed16-0dcb-453c-b011-cf0fee63d355`.
- Staging URLs: <https://frontend-staging-8dc6.up.railway.app/> and <https://backend-staging-566d.up.railway.app/>.
- Prior frontend-to-API preflight failed because old staging code predates the CORS fix; expected to pass after direct main push and redeploy.

## Direct-main operating rule

Run applicable local checks, then push reviewed/ready commits directly to `main`; no issue or PR is required by the observed GitHub repository settings. Every `main` push auto-deploys staging. Verify staging before making a separate explicit production promotion. Do not put production auto-deploy back on.
