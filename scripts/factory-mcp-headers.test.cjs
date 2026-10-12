'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');
const helper = path.join(__dirname, 'factory-mcp-headers.cjs');

function fixture(t, dotenv) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'factory headers-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'scripts'));
  fs.copyFileSync(helper, path.join(root, 'scripts', path.basename(helper)));
  if (dotenv !== null) fs.writeFileSync(path.join(root, '.env'), dotenv);
  return root;
}

function run(root) {
  return spawnSync(process.execPath, [path.join(root, 'scripts', path.basename(helper))], {
    cwd: os.tmpdir(), encoding: 'utf8',
    env: { ...process.env, LA_FABRICA_MCP_TOKEN: 'wrong-host-token' },
  });
}

test('reads project dotenv from another cwd without forwarding unrelated keys', (t) => {
  const root = fixture(t, 'LA_FABRICA_MCP_TOKEN = "fake-project-token"\nOTHER_SECRET=private-other\n');
  const result = run(root);
  assert.equal(result.status, 0);
  assert.equal(result.stderr, '');
  assert.deepEqual(JSON.parse(result.stdout), { Authorization: 'Bearer fake-project-token' });
  assert.equal(result.stdout.includes('private-other'), false);
  assert.equal(result.stdout.includes('wrong-host-token'), false);
});

for (const [name, dotenv] of [
  ['missing file', null], ['missing key', 'OTHER_SECRET=private-other'],
  ['empty token', 'LA_FABRICA_MCP_TOKEN="   "'],
  ['header injection', 'LA_FABRICA_MCP_TOKEN="fake\nAuthorization: leaked"'],
]) {
  test(`fails safely for ${name}`, (t) => {
    const result = run(fixture(t, dotenv));
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.equal(result.stderr, 'Unable to load a valid La Fabrica token from project .env.\n');
  });
}

test('CLI wrapper selects the native helper without copying dotenv into child env', (t) => {
  const root = fixture(t, 'LA_FABRICA_MCP_TOKEN=fake-project-token\nOTHER_SECRET=private-other\n');
  fs.copyFileSync(path.join(__dirname, 'start-codex-factory.cjs'), path.join(root, 'scripts/start-codex-factory.cjs'));
  fs.copyFileSync(path.join(__dirname, '../MCP.json'), path.join(root, 'MCP.json'));
  const cli = path.join(root, 'fake-cli.cjs');
  fs.writeFileSync(cli, 'console.log(JSON.stringify({args:process.argv.slice(2), token:process.env.LA_FABRICA_MCP_TOKEN, cwd:process.cwd()}));');
  const env = { ...process.env };
  delete env.LA_FABRICA_MCP_TOKEN;
  const result = spawnSync(process.execPath, ['-e',
    'process.exitCode=require(process.argv[1]).main(process.argv[2],process.argv[3],["mcp","get","la_fabrica"]);',
    path.join(root, 'scripts/start-codex-factory.cjs'), root, cli], { env, encoding: 'utf8' });
  assert.equal(result.status, 0);
  const received = JSON.parse(result.stdout);
  assert.equal(received.token, undefined);
  assert.equal(received.cwd, root);
  assert.deepEqual(received.args.slice(-3), ['mcp', 'get', 'la_fabrica']);
  assert.ok(received.args.some(arg => arg.startsWith('mcp_servers.la_fabrica.http_headers_helper=')));
  assert.equal(result.stdout.includes('fake-project-token'), false);
  assert.equal(result.stdout.includes('private-other'), false);
});
