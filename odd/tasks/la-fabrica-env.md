# La Fabrica dotenv integration

## Objective
Connect Codex to La Fabrica using the existing local `.env` as the only token source, install the official deployment skill, and read the project board.

## Scope and constraints
- Preserve existing MCP servers, preferences, and `.env` contents.
- Never expose token values in output, arguments, committed files, URLs, or logs.
- Add a launcher-owned `MCP.json` and native project `.codex/config.toml`.
- Use only authenticated skill download and read-only MCP initialization, discovery, and `sf_board`; never call `sf_write`.
- Install the official skill under `.agents/skills/agedrex-factory/` without overwriting existing files.

## Tasks
- [x] T1: Ignore `.env`, add native MCP configuration and a dotenv launcher with `MCP.json`; verify safe token inheritance and configuration.
- [x] T2: Download and inspect the official skill; validate `sf_*` discovery and read `sf_board`; record reload requirements.

## Routing and checks
- T1/T2: delegated direct; multiple non-trivial files and preparation for writing require a bounded worker.
- Use Node built-in dotenv parsing. RED/GREEN applies to deterministic launcher validation using a fake token and fake child; remote availability has no meaningful deterministic RED.
- Check launcher syntax, fake token inheritance, `.env` exclusion, native MCP configuration, safe ZIP paths, actual MCP discovery/board, and `git diff --check`.
- Independent verification and one parent spot check follow implementation.
- Work-unit commits use a feature branch and Conventional Commits. No push or PR is authorized.

## Delivery
- Strategy: ask-on-risk. Forecast: approximately 200 authored lines, excluding downloaded skill content.
- T1 checks: RED observed missing launcher before implementation; GREEN temporary fake-child harness passed token inheritance, selective loading, argument preservation, project cwd, and sanitized missing-token failure. `node --check` passed. `git check-ignore .env` passed. Launcher `mcp get la_fabrica` confirmed enabled Streamable HTTP and variable-name authentication; sandbox home-directory access failed, escalated execution passed.
- Native Codex reads `.codex/config.toml`; `MCP.json` is the launcher's validated manifest. The launcher supplies only public URL and token-variable name as Codex config overrides so CLI inspection also works before project trust is established.
- Launch a new session with `node scripts/start-codex-factory.cjs` from this repository. Existing sessions cannot inherit the new child environment or discover the installed skill in this setup.
- T1 rollback boundary: remove the launcher, its manifest and project MCP entry; keep `.env` excluded from Git.
- T1 commit: `5b5fabd` (`feat(mcp): launch Codex with La Fabrica token from local dotenv`).
- T2 checks: authenticated deployment download succeeded after sandbox network failure and escalation. All 24 ZIP files passed path, duplicate, encryption, symlink, decompression-size, overwrite and exact-secret checks before installation. Read the official `agedrex-factory/SKILL.md`.
- MCP initialize, initialized notification, tools/list and read-only `sf_board({})` succeeded. Discovered 14 `sf_*` tools. No write tools were called.
- Board: Casa Lopez - Projecto1 has 7 requirements, 2 blueprints and 5 work orders; WO-1, WO-2, WO-4 and WO-5 are in progress, WO-3 is ready. None are blocked or in review. E1 is in progress without dates.
- Final `git diff --check`, launcher syntax, and exact-secret scan across tracked files plus new configuration and skill files passed. T2 commit identity will be available in Git history under `feat(skills): install official La Fabrica deployment workflow`.
- Authored change count: approximately 132 lines; downloaded skill files excluded. RDD remains off; native risk assessment unavailable/high. Independent verification pending.
- T2 rollback boundary: remove `.agents/skills/agedrex-factory/`; remote calls changed no project records.
- Engram mirror: pending; mutation hook rejected this runtime session as unregistered.

## Current evidence
- Codex CLI 0.162.1 and Node 24.21.0 are installed.
- `.env` has a non-empty `LA_FABRICA_MCP_TOKEN`; values were never displayed.
- `.env` is untracked and not ignored. The branch is `main`.
- Native HTTP MCP reads `bearer_token_env_var`; existing session environment cannot be retroactively updated by a child process.

## Next step
Parent independent verification and final user delivery. Launch a new Codex session with the provided launcher for native MCP tools and skill discovery.
