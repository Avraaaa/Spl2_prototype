#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import assert from 'node:assert/strict';
const root = resolve(import.meta.dirname, '..');
const read = path => readFileSync(join(root, path), 'utf8');
const required = ['AGENTS.template.md','CLAUDE.md','compose.yaml','compose.prod.yaml','implementation.md','docs/tasks.json','docs/traceability.csv','.claude/settings.json','.codex/config.toml','.github/workflows/ci.yml','services/api/pyproject.toml','services/ml/pyproject.toml','pyproject.toml','scripts/bootstrap-agents.mjs'];
for (const path of required) assert(existsSync(join(root,path)), `Missing ${path}`);
assert(read('CLAUDE.md').includes('@AGENTS.md'));
const ignore = read('.gitignore');
for (const pattern of ['AGENTS.md','agents.md']) assert(ignore.split(/\r?\n/).includes(pattern), `Missing gitignore ${pattern}`);
assert(read('AGENTS.template.md').includes('uv is mandatory'));
assert(!read('services/api/Dockerfile').includes('pip install'));
assert(!read('services/ml/Dockerfile').includes('pip install'));
const tasks = JSON.parse(read('docs/tasks.json'));
const seen = new Set();
for (const task of tasks.tasks) {
 assert(!seen.has(task.id), `Duplicate task ${task.id}`);
 assert(task.depends_on.every(id => seen.has(id)), `Bad dependency order: ${task.id}`);
 assert(task.allow.length && task.req.length && task.gates.length, `Incomplete ${task.id}`);
 assert(task.gates.every(cmd => !/(^|\s)(python|pip|pytest|ruff|mypy)(?=\s|$)/.test(cmd) || cmd.includes('uv run')), `Unmanaged Python command in ${task.id}`);
 seen.add(task.id);
}
const rows = read('docs/traceability.csv').trim().split(/\r?\n/).slice(1);
const reqIds = new Set(rows.map(row => row.split(',')[0]));
assert(reqIds.size === 55, `Expected 55 requirement IDs, found ${reqIds.size}`);
for (const section of ['apps/web','services/api','services/ml','infra']) assert(existsSync(join(root,section,'AGENTS.template.md')));
JSON.parse(read('.claude/settings.json'));
console.log(`PASS: ${required.length} required files, ${seen.size} ordered tasks, ${reqIds.size} requirement IDs; uv policy and gitignore verified.`);
