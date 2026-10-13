#!/usr/bin/env node
// Returns the next free zero-padded ID for a given SDLC artifact type by scanning the docs/sdlc/<dir>/ folder.
// Usage: node scripts/next-id.js <type>
// Types: roadmap|requirement|task|design|adr|test|deployment|operation|sprint

import { readdirSync } from 'node:fs';
import { join } from 'node:path';

const MAP = {
  roadmap:     { dir: '01-roadmap',      prefix: 'ROADMAP' },
  requirement: { dir: '02-requirements', prefix: 'REQ' },
  design:      { dir: '03-designs',      prefix: 'DES' },
  adr:         { dir: '04-adrs',         prefix: 'ADR' },
  task:        { dir: '05-tasks',        prefix: 'TASK' },
  sprint:      { dir: '06-sprints',      prefix: 'SPRINT' },
  test:        { dir: '07-tests',        prefix: 'TEST' },
  deployment:  { dir: '08-deployments',  prefix: 'DEP' },
  operation:   { dir: '09-operations',   prefix: 'OPS' }
};

const PAD = 4;

const type = process.argv[2];
if (!type || !MAP[type]) {
  console.error('Usage: node scripts/next-id.js <type>');
  console.error('Types: ' + Object.keys(MAP).join('|'));
  process.exit(2);
}

const { dir, prefix } = MAP[type];
const base = join('docs', 'sdlc', dir);
let max = 0;
try {
  for (const f of readdirSync(base)) {
    const m = f.match(new RegExp(`^${prefix}-(\\d+)`));
    if (m) max = Math.max(max, Number(m[1]));
  }
} catch (e) {
  if (e.code !== 'ENOENT') throw e;
}
const next = (max + 1).toString().padStart(PAD, '0');
process.stdout.write(`${prefix}-${next}\n`);
