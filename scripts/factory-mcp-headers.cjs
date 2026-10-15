#!/usr/bin/env node
'use strict';

// Codex captures this command's stdout as HTTP headers; never run it for display.
const fs = require('node:fs');
const path = require('node:path');
const { parseEnv } = require('node:util');

function main(root = path.resolve(__dirname, '..')) {
  try {
    const token = parseEnv(fs.readFileSync(path.join(root, '.env'), 'utf8')).LA_FABRICA_MCP_TOKEN;
    if (!token || !/^[A-Za-z0-9._~+/-]+=*$/.test(token)) throw new Error('Invalid token');
    process.stdout.write(JSON.stringify({ Authorization: `Bearer ${token}` }) + '\n');
    return 0;
  } catch {
    console.error('Unable to load a valid La Fabrica token from project .env.');
    return 1;
  }
}

module.exports = { main };
if (require.main === module) process.exitCode = main();
