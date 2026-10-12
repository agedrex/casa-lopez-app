# La Fabrica dotenv integration

## Objective
Connect Codex to La Fabrica using the existing local `.env` as the only token source, install the official deployment skill, and read the project board.

## Scope and constraints
- Preserve existing MCP servers, preferences, and `.env` contents.
- Never expose token values in user-visible output, arguments, committed files, URLs, or logs. The native header helper returns its JSON only through Codex's private capture pipe.
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
- Final `git diff --check`, launcher syntax, and exact-secret scan across tracked files plus new configuration and skill files passed. T2 commit: `bcaa8ea` (`feat(skills): install official La Fabrica deployment workflow`).
- Authored change count: approximately 132 lines; downloaded skill files excluded. RDD remains off; native risk assessment unavailable/high. Independent verification passed: six fake-child/security cases, syntax, dotenv exclusion, clean tree, and installed skill file count. Parent spot check repeated launcher syntax successfully.
- T2 rollback boundary: remove `.agents/skills/agedrex-factory/`; remote calls changed no project records.
- Engram mirror: pending; mutation hook rejected this runtime session as unregistered.

## Current evidence
- Codex CLI 0.162.1 and Node 24.21.0 are installed.
- `.env` has a non-empty `LA_FABRICA_MCP_TOKEN`; values were never displayed.
- `.env` is untracked and ignored. The branch is `feat/la-fabrica-env`.
- T1 used `bearer_token_env_var`, but normal desktop startup did not inherit a token loaded only by the CLI wrapper. T3 replaces that dependency with native `http_headers_helper` loading project dotenv directly.

## Desktop connection repair
- [x] T3: Load project dotenv through a native HTTP header helper so normal desktop startup does not require a custom launcher or exported token; verify fake-token isolation, actual native helper execution, and authenticated remote discovery.
- Route: delegated direct; helper, launcher, configuration and meaningful tests require multiple non-trivial changes.
- Authorized surfaces: `.codex/config.toml`, `scripts/factory-mcp-headers.cjs`, `scripts/factory-mcp-headers.test.cjs`, `scripts/start-codex-factory.cjs`, `MCP.json`, this task document. Preserve `.env` and all global configuration.
- Acceptance: native Streamable HTTP authentication works with the host token variable absent; helper resolves dotenv from project location and never leaks tokens in errors or arguments.
- Checks: Node syntax, deterministic RED/GREEN tests, installed Codex local fake MCP initialize/tools discovery, authenticated remote initialize/tools discovery, Git whitespace and tracked-secret checks.
- Forecast: approximately 200 additional authored lines. Delivery strategy remains ask-on-risk; no push or PR authorized.
- Engram mirror remains pending: the memory hook refuses this unregistered runtime session; no session identity was invented.
- Implementation: `.codex/config.toml` retains native Streamable HTTP and invokes `factory-mcp-headers.cjs` with explicit installed Node/project paths. These paths match this Windows workstation; update them if relocating the project or Node installation. The helper anchors dotenv to its own directory and validates bearer-token characters. No global configuration or dotenv content changed.
- CLI compatibility: the optional launcher now supplies the same header-helper override; it no longer copies project dotenv into its child environment. `MCP.json` remains a public launcher manifest.
- Verification: RED observed five missing-helper tests before implementation. GREEN passed six deterministic tests covering project dotenv resolution from another cwd, unrelated-key exclusion, host-token isolation, missing file/key, empty token, newline injection, and wrapper argument/env behavior. Both scripts passed `node --check`; `git diff --check` passed.
- Native runtime proof: `node $env:TEMP/factory-native-helper-check.cjs` launched installed Codex 0.162.1 `app-server --strict-config` against a local fake HTTP MCP using fake dotenv and no host token variable. It ran from a different cwd, authenticated initialize and discovery, and returned the fixture tool through `mcpServerStatus/list`. No model turns or paid API calls were made.
- Remote runtime proof: `node $env:TEMP/factory-helper-remote-check.cjs` captured helper output privately, then successfully initialized and discovered all 14 `sf_*` tools at the existing Railway URL. Sandbox networking failed; approved escalation succeeded. Only initialize, initialized notification and tools/list were sent; no remote records changed.
- Independent verification passed all six tests, both syntax checks, dotenv exclusion and whitespace checks. Parent syntax spot check and exact-secret scan passed. Native risk assessment failed with repository access denied (unassessable/high); RDD remains off, and independent verification covers closure under ordinary policy.
- Work-unit commit: `3ecf235` (`fix(mcp): authenticate La Fabrica from project dotenv on app startup`), 110 authored changed lines. Accumulated feature changes remain below the approximate 400-line delivery budget.
- Rollback boundary: revert T3 project config/launcher/manifest changes and remove the helper/test files; retain ignored `.env` and installed skill.

## Next step
Restart Codex to activate the native helper in a new project session. Normal startup no longer requires the optional CLI launcher or an exported token. Engram mirror remains pending due to the unregistered host session.
