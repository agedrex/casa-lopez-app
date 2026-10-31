# Cutting role

## Objective
Add an assignable cutting role with access only to Cutting, Leather, and Voice, while preserving all existing write permissions.

## Scope and constraints
- Branch: `feat/rol-corte` from updated `main`.
- No database migrations or changes to existing write gates.
- Keep the existing local `.codex/config.toml` and `front/public/` changes untouched.
- Push only the feature branch; prepare PR text without using `gh`.

## Tasks
- [x] T1 (inline): Add role definition, route guards, navigation, and placeholder pages. Frontend build and Biome passed.
- [x] T2 (inline): Prepare the future cutting dependency and prove current writes reject the cutting role. Backend tests passed in CI.
- [x] T3 (inline): Review the diff, commit the work unit, push the feature branch, and prepare PR title and body.

## Acceptance criteria
- Admin users can be assigned `corte`; `consulta` displays as Gerente without changing its stored value.
- A cutting-only user can open only `/corte`, `/cueros`, and `/voz`; other app paths redirect to `/corte` in the proxy and server layout.
- Cutting navigation and mobile quick actions show only the requested destinations; other roles retain their current bar.
- Existing backend POST routes still return 403 to `corte`.

## Verification
- `uv run --directory backend pytest -q` (CI fallback if unavailable)
- `cd front && corepack pnpm build`
- Biome check on touched frontend files

## Progress
- Branch created from up-to-date main.
- `/cueros` did not exist, so a minimal placeholder was added to keep the requested navigation usable.
- Frontend build passed; Biome passed on eight touched frontend files.
- Work-unit commit: `dff96e8` (`feat(auth): add restricted cutting role`).
- `uv` is unavailable locally, and the existing backend virtual environment points to a missing Python interpreter; CI runs the exact requested test command on push.
- CI run `41220844055` passed Backend tests and Frontend lint and build on commit `dff96e8`.
- Feature branch `feat/rol-corte` was pushed to `origin`; no push to `main` and no merge.
- Engram mirror pending because the host session is unregistered.
- T1 route: inline, as the user expressly prohibited helper agents; the change spans several files.
- T2 route: inline, as the user expressly prohibited helper agents; focused regression proof required.
- T3 route: inline, Git and delivery state.
- Forecast: approximately 150 authored changed lines, one work-unit commit.
- Next: open a pull request with the prepared title and body; this task does not create it.
