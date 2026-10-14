#!/usr/bin/env node
// Walks docs/sdlc/**/*.md, parses frontmatter, emits docs/sdlc/_graph.json and docs/sdlc/_graph.mmd.
// Zero deps — uses a tiny inline YAML-frontmatter parser (same subset as the skill's lib/frontmatter.js).

import { readdirSync, readFileSync, writeFileSync, statSync, mkdirSync, existsSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const ROOT = join('docs', 'sdlc');
const EDGE_FIELDS = ['advances', 'implements', 'designed_by', 'verified_by', 'deployed_in', 'blocks', 'blocked_by', 'related', 'adrs'];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) {
      if (name.startsWith('_')) continue; // skip _templates etc.
      walk(p, out);
    } else if (name.endsWith('.md')) {
      out.push(p);
    }
  }
  return out;
}

function split(text) {
  if (!text.startsWith('---\n')) return { fm: '', body: text };
  const rest = text.slice(4);
  const end = rest.indexOf('\n---');
  if (end < 0) return { fm: '', body: text };
  return { fm: rest.slice(0, end), body: rest.slice(end + 4) };
}

function parse(fm) {
  const obj = {};
  for (const line of fm.split('\n')) {
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/);
    if (!m) continue;
    const v = m[2].trim();
    if (v.startsWith('[') && v.endsWith(']')) {
      const inner = v.slice(1, -1).trim();
      obj[m[1]] = inner ? inner.split(',').map(s => s.trim().replace(/^["']|["']$/g, '')) : [];
    } else {
      obj[m[1]] = v.replace(/^["']|["']$/g, '');
    }
  }
  return obj;
}

const root = process.cwd();
const docsRoot = join(root, ROOT);
if (!existsSync(docsRoot)) {
  console.error(`No ${ROOT}/ directory. Run from your project root.`);
  process.exit(2);
}

const files = walk(docsRoot);
const nodes = [];
const edges = [];
const knownIds = new Set();

for (const f of files) {
  const txt = readFileSync(f, 'utf8');
  const { fm } = split(txt);
  if (!fm) continue;
  const m = parse(fm);
  if (!m.id) continue;
  knownIds.add(m.id);
  nodes.push({
    id: m.id,
    type: m.type || '',
    title: m.title || '',
    status: m.status || '',
    owner: m.owner || '',
    risk: m.risk || '',
    path: relative(root, f).split(sep).join('/')
  });
}

for (const f of files) {
  const txt = readFileSync(f, 'utf8');
  const { fm } = split(txt);
  if (!fm) continue;
  const m = parse(fm);
  if (!m.id) continue;
  for (const field of EDGE_FIELDS) {
    const list = m[field];
    if (!Array.isArray(list)) continue;
    for (const target of list) {
      if (!target) continue;
      edges.push({ from: m.id, to: target, type: field, dangling: !knownIds.has(target) });
    }
  }
}

writeFileSync(join(docsRoot, '_graph.json'), JSON.stringify({ nodes, edges }, null, 2) + '\n');

const dangling = edges.filter(e => e.dangling);
if (dangling.length) {
  console.warn(`Warning: ${dangling.length} dangling edge(s):`);
  for (const e of dangling) console.warn(`  ${e.from} -[${e.type}]-> ${e.to} (target not found)`);
}

// Mermaid
const lines = ['graph LR'];
for (const n of nodes) {
  const label = `${n.id}\\n${(n.title || '').slice(0, 40)}`;
  lines.push(`  ${safe(n.id)}["${label}"]`);
}
for (const e of edges) {
  if (e.dangling) continue;
  lines.push(`  ${safe(e.from)} -->|${e.type}| ${safe(e.to)}`);
}
writeFileSync(join(docsRoot, '_graph.mmd'), lines.join('\n') + '\n');

console.log(`Wrote ${nodes.length} nodes, ${edges.length} edges to ${ROOT}/_graph.json and _graph.mmd`);

function safe(id) { return id.replace(/[^A-Za-z0-9_]/g, '_'); }
