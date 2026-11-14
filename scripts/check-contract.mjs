#!/usr/bin/env node
// Backend-generated OpenAPI is authoritative. Runs natively (no Docker) through uv + npm.
//   node scripts/check-contract.mjs          fail if contracts/openapi.yaml or schema.d.ts is stale
//   node scripts/check-contract.mjs --write  regenerate both files
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = resolve(import.meta.dirname, '..');
const write = process.argv.includes('--write');
const contract = join(root, 'contracts/openapi.yaml');
const types = join(root, 'apps/web/src/api/generated/schema.d.ts');
// Schema generation imports settings only; it needs no database or real secret.
const env = { DJANGO_DEBUG: '1', ...process.env };
const run = (cmd, args) => {
  // shell:true resolves npm.cmd on Windows; arguments are fixed, not user input.
  const proc = spawnSync([cmd, ...args].join(' '), { cwd: root, encoding: 'utf8', stdio: 'pipe', env, shell: true });
  if (proc.status !== 0) throw new Error(`${cmd} ${args.join(' ')} failed: ${proc.stderr || proc.stdout}`);
  return proc.stdout;
};
const norm = text => text.replace(/\r\n/g, '\n');
const dir = mkdtempSync(join(tmpdir(), 'datasoft-contract-'));
try {
  const fresh = join(dir, 'openapi.yaml');
  run('uv', ['run', '--locked', '--package', 'datasoft-api', 'python', 'services/api/manage.py',
    'spectacular', '--file', `"${fresh}"`, '--validate', '--fail-on-warn']);
  const actual = readFileSync(fresh, 'utf8');
  if (write) writeFileSync(contract, actual);
  else if (norm(actual) !== norm(readFileSync(contract, 'utf8'))) throw new Error('Committed OpenAPI is stale: run with --write');

  const original = existsSync(types) ? readFileSync(types, 'utf8') : '';
  run('npm', ['run', '--prefix', 'apps/web', 'generate:api']);
  if (!write && norm(original) !== norm(readFileSync(types, 'utf8'))) {
    writeFileSync(types, original);
    throw new Error('Generated TypeScript types are stale: run with --write');
  }
  console.log(write ? 'WROTE: contracts/openapi.yaml and schema.d.ts' : 'PASS: OpenAPI and TypeScript client match.');
} catch (error) {
  console.error(`FAIL: ${error.message}`);
  process.exitCode = 1;
} finally { rmSync(dir, { recursive: true, force: true }); }
