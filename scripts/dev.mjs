#!/usr/bin/env node
/**
 * Native (Windows/macOS/Linux) local development launcher. No Docker required.
 *
 *   node scripts/dev.mjs            migrate, then run Django (8000) + Vite (5173)
 *   node scripts/dev.mjs api|web|ml  run one service
 *   node scripts/dev.mjs migrate     apply Django migrations
 *   node scripts/dev.mjs seed        load synthetic demo banks/users/issues
 *   node scripts/dev.mjs test        Django + FastAPI + web checks
 *   node scripts/dev.mjs lint        ruff check, ruff format --check, mypy
 *   node scripts/dev.mjs manage ...  any manage.py command
 *
 * The defaults below are SYNTHETIC LOCAL-ONLY values that match scripts/dev-db-setup.sql.
 * Any variable already present in the environment wins. Never put real credentials here.
 */
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const devDefaults = {
  DJANGO_DEBUG: '1',
  DJANGO_SECRET_KEY: 'local-dev-only-not-a-secret',
  DJANGO_ALLOWED_HOSTS: 'localhost,127.0.0.1',
  DJANGO_CSRF_TRUSTED_ORIGINS: 'http://localhost:5173,http://127.0.0.1:5173',
  POSTGRES_DB: 'datasoft',
  POSTGRES_USER: 'datasoft',
  POSTGRES_PASSWORD: 'datasoft-local-dev',
  DATABASE_HOST: 'localhost',
  DATABASE_PORT: '5432',
  ML_MODEL_ENABLED: '0',
  PYTHONUTF8: '1',
};
const env = { ...devDefaults, ...process.env };

const api = ['uv', 'run', '--locked', '--package', 'datasoft-api'];
const manage = (...a) => [...api, 'python', 'services/api/manage.py', ...a];
const commands = {
  migrate: [manage('migrate', '--noinput')],
  seed: [manage('seed_demo')],
  api: [manage('runserver', '127.0.0.1:8000')],
  web: [['npm', 'run', '--prefix', 'apps/web', 'dev']],
  ml: [['uv', 'run', '--locked', '--package', 'datasoft-ml', '--directory', 'services/ml',
    'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001']],
  test: [
    [...api, 'pytest', '-q', 'services/api/tests'],
    ['uv', 'run', '--locked', '--package', 'datasoft-ml', 'pytest', '-q', 'services/ml/tests'],
    ['npm', 'run', '--prefix', 'apps/web', 'check'],
  ],
  lint: [
    ['uv', 'run', '--locked', 'ruff', 'check', 'services'],
    ['uv', 'run', '--locked', 'ruff', 'format', '--check', 'services'],
    ['uv', 'run', '--locked', 'mypy', 'services/api', '--config-file', 'pyproject.toml'],
  ],
};

function quote(arg) {
  return /^[\w@%+=:,./\\-]+$/.test(arg) ? arg : `"${arg.replaceAll('"', '\\"')}"`;
}
function start(argv, label) {
  // shell:true is needed to resolve npm.cmd on Windows; arguments are fixed above, not user input.
  const child = spawn(argv.map(quote).join(' '), { cwd: root, env, shell: true, stdio: label ? 'pipe' : 'inherit' });
  if (label) {
    const prefix = chunk => chunk.toString().split(/\r?\n/).filter(Boolean).map(l => `[${label}] ${l}`).join('\n') + '\n';
    child.stdout.on('data', c => process.stdout.write(prefix(c)));
    child.stderr.on('data', c => process.stderr.write(prefix(c)));
  }
  return child;
}
const runOnce = argv => new Promise(res => start(argv).on('exit', code => res(code ?? 1)));

async function sequence(list) {
  for (const argv of list) {
    const code = await runOnce(argv);
    if (code !== 0) { console.error(`FAILED (exit ${code}): ${argv.join(' ')}`); process.exit(code); }
  }
}

const [cmd = 'all', ...rest] = process.argv.slice(2);
if (cmd === 'manage') await sequence([manage(...rest)]);
else if (cmd === 'all') {
  await sequence(commands.migrate);
  const children = [start(commands.api[0], 'api'), start(commands.web[0], 'web')];
  console.log('API http://127.0.0.1:8000/api/health/  |  Web http://localhost:5173  (Ctrl+C to stop)');
  const stop = () => { for (const c of children) c.kill(); process.exit(0); };
  process.on('SIGINT', stop);
  for (const c of children) c.on('exit', code => { if (code) console.error(`a service exited with ${code}`); });
} else if (commands[cmd]) await sequence(commands[cmd]);
else { console.error(`Unknown command ${cmd}. Use: all|api|web|ml|migrate|seed|test|lint|manage`); process.exit(2); }
