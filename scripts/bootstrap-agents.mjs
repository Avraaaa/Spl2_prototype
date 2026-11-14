#!/usr/bin/env node
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const dirs = ['', 'apps/web', 'services/api', 'services/ml', 'infra'];
for (const dir of dirs) {
  const input = join(root, dir, 'AGENTS.template.md');
  const output = join(root, dir, 'AGENTS.md');
  if (!existsSync(input)) throw new Error(`Missing source instructions: ${input}`);
  const source = readFileSync(input, 'utf8');
  if (existsSync(output) && readFileSync(output, 'utf8') !== source && process.argv.includes('--check')) {
    throw new Error(`Local instructions are stale: ${output}`);
  }
  if (!process.argv.includes('--check')) writeFileSync(output, source);
}
console.log(process.argv.includes('--check') ? 'Local agent files are in sync' : 'Generated 5 ignored AGENTS.md files from tracked templates.');
