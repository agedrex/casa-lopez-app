#!/usr/bin/env node
'use strict';

// Launch Codex with La Fabrica's native dotenv HTTP header helper.
// Native MCP configuration lives in .codex/config.toml, not MCP.json.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

function fail(message) {
  console.error(message);
  return 1;
}

function findCodex() {
  const prefixes = [
    process.env.APPDATA && path.join(process.env.APPDATA, 'npm'),
    process.env.npm_config_prefix,
    path.dirname(process.execPath),
    path.join(os.homedir(), '.npm-global'),
    '/usr/local',
    '/usr',
  ].filter(Boolean);
  for (const prefix of prefixes) {
    for (const modules of ['node_modules', 'lib/node_modules']) {
      const candidate = path.join(prefix, modules, '@openai', 'codex', 'bin', 'codex.js');
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  throw new Error('Codex installation unavailable');
}

function main(root = path.resolve(__dirname, '..'), cliPath, args = process.argv.slice(2)) {
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'MCP.json'), 'utf8'));
    const server = manifest.mcpServers?.la_fabrica;
    if (server?.url !== 'https://backend-production-49aca.up.railway.app/mcp/' ||
        server?.bearer_token_env_var !== 'LA_FABRICA_MCP_TOKEN') {
      return fail('Invalid La Fabrica launcher manifest.');
    }
    // Overrides also let inspection commands work before project trust is set.
    // The helper reads dotenv directly; no token enters arguments or child env.
    const helper = `"${process.execPath.replaceAll('\\', '/')}" "${path.join(root, 'scripts', 'factory-mcp-headers.cjs').replaceAll('\\', '/')}"`;
    const result = spawnSync(process.execPath, [cliPath || findCodex(),
      '-c', `mcp_servers.la_fabrica.url=${JSON.stringify(server.url)}`,
      '-c', `mcp_servers.la_fabrica.http_headers_helper=${JSON.stringify(helper)}`,
      ...args], {
      cwd: root,
      env: process.env,
      stdio: 'inherit',
      shell: false,
    });
    if (result.error) return fail('Unable to start Codex. Check the local installation.');
    return result.status ?? 1;
  } catch {
    return fail('Unable to load local La Fabrica configuration or Codex installation.');
  }
}

module.exports = { main };
if (require.main === module) process.exitCode = main();
