#!/usr/bin/env node
// Apply status-propagation rules across linked SDLC docs.
// Usage: node scripts/sdlc-propagate.js <path-to-changed-doc.md>

import { readdirSync, readFileSync, writeFileSync, statSync, existsSync } from 'node:fs';
import { join, relative, sep, resolve } from 'node:path';

const ROOT = join('docs', 'sdlc');

function today() {
  // Allow override for tests (avoid wall-clock flake in plans).
  return process.env.SDLC_TODAY || new Date().toISOString().slice(0, 10);
}

function split(text) {
  if (!text.startsWith('---\n')) return { fm: '', body: text };
  const rest = text.slice(4);
  const end = rest.indexOf('\n---');
  if (end < 0) return { fm: '', body: text };
  return { fm: rest.slice(0, end), body: rest.slice(end + 5) };
}

function parse(fm) {
  const obj = {};
  for (const line of fm.split('\n')) {
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/);
    if (!m) continue;
    obj[m[1]] = parseValue(m[2]);
  }
  return obj;
}

function parseValue(raw) {
  const v = raw.trim();
  if (v.startsWith('[') && v.endsWith(']')) {
    const inner = v.slice(1, -1).trim();
    return inner ? inner.split(',').map(s => s.trim().replace(/^["']|["']$/g, '')) : [];
  }
  if (v.startsWith('{') && v.endsWith('}')) {
    const inner = v.slice(1, -1).trim();
    if (!inner) return {};
    const out = {};
    for (const part of inner.split(',')) {
      const i = part.indexOf(':');
      if (i < 0) continue;
      out[part.slice(0, i).trim()] = parseValue(part.slice(i + 1).trim());
    }
    return out;
  }
  return v.replace(/^["']|["']$/g, '');
}

function serialize(obj) {
  const lines = [];
  for (const [k, v] of Object.entries(obj)) {
    lines.push(`${k}: ${serializeValue(v)}`);
  }
  return lines.join('\n') + '\n';
}

function serializeValue(v) {
  if (Array.isArray(v)) return '[' + v.join(', ') + ']';
  if (v && typeof v === 'object') {
    return '{' + Object.entries(v).map(([k, vv]) => `${k}: ${vv}`).join(', ') + '}';
  }
  return String(v);
}

function readDoc(path) {
  const text = readFileSync(path, 'utf8');
  const { fm, body } = split(text);
  return { fm: parse(fm), body, path };
}

function writeDoc(d) {
  writeFileSync(d.path, '---\n' + serialize(d.fm) + '---\n' + d.body);
}

function findById(root, id) {
  const docsRoot = join(root, ROOT);
  const stack = [docsRoot];
  while (stack.length) {
    const dir = stack.pop();
    if (!existsSync(dir)) continue;
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) {
        if (name.startsWith('_')) continue;
        stack.push(p);
      } else if (name.endsWith('.md')) {
        const { fm } = split(readFileSync(p, 'utf8'));
        const m = parse(fm);
        if (m.id === id) return p;
      }
    }
  }
  return null;
}

function setStatus(d, status, note) {
  d.fm.status = status;
  d.fm.updated = today();
  if (note) d.body += (d.body.endsWith('\n') ? '' : '\n') + `> note: ${note}\n`;
}

const root = process.cwd();
const target = process.argv[2];
if (!target) {
  console.error('Usage: node scripts/sdlc-propagate.js <path-to-doc.md>');
  process.exit(2);
}
const abs = resolve(target);
const changed = readDoc(abs);
const touched = new Set([abs]);

const id = changed.fm.id;
const type = changed.fm.type;
const status = changed.fm.status;

// Rule: task -> done with any verified_by test failing => revert to blocked
if (type === 'task' && status === 'done' && Array.isArray(changed.fm.verified_by)) {
  let failing = false;
  for (const testId of changed.fm.verified_by) {
    const p = findById(root, testId);
    if (!p) continue;
    const t = readDoc(p);
    const lr = t.fm.last_run;
    if (lr && typeof lr === 'object' && lr.result && lr.result !== 'pass') { failing = true; break; }
  }
  if (failing) {
    setStatus(changed, 'blocked', 'reverted to blocked: a verified_by test is not passing');
    writeDoc(changed);
  }
}

// Rule: task -> blocked propagates blocked to blocks list
if (type === 'task' && changed.fm.status === 'blocked' && Array.isArray(changed.fm.blocks)) {
  for (const tid of changed.fm.blocks) {
    const p = findById(root, tid);
    if (!p) continue;
    const d = readDoc(p);
    if (d.fm.status !== 'blocked' && d.fm.status !== 'done' && d.fm.status !== 'cancelled') {
      setStatus(d, 'blocked', `blocked transitively by ${id}`);
      writeDoc(d);
      touched.add(p);
    }
  }
}

// Rule: requirement -> cancelled cancels implementing tasks that are not done
if (type === 'requirement' && status === 'cancelled') {
  const docsRoot = join(root, ROOT, '05-tasks');
  if (existsSync(docsRoot)) {
    for (const name of readdirSync(docsRoot)) {
      const p = join(docsRoot, name);
      if (!name.endsWith('.md')) continue;
      const d = readDoc(p);
      if (Array.isArray(d.fm.implements) && d.fm.implements.includes(id) && d.fm.status !== 'done') {
        setStatus(d, 'cancelled', `cancelled because ${id} was cancelled`);
        writeDoc(d);
        touched.add(p);
      }
    }
  }
}

// Rule: deployment -> done stamps deployed_in on each artifact task
if (type === 'deployment' && status === 'done' && Array.isArray(changed.fm.artifacts)) {
  for (const tid of changed.fm.artifacts) {
    const p = findById(root, tid);
    if (!p) continue;
    const d = readDoc(p);
    const cur = Array.isArray(d.fm.deployed_in) ? d.fm.deployed_in : [];
    if (!cur.includes(id)) {
      d.fm.deployed_in = [...cur, id];
      d.fm.updated = today();
      writeDoc(d);
      touched.add(p);
    }
  }
}

console.log('Propagation touched ' + touched.size + ' file(s):');
for (const p of touched) console.log('  ' + relative(root, p).split(sep).join('/'));
