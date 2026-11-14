#!/usr/bin/env node
/**
 * Local synthetic-data task harness. This is not a security sandbox or an assurance of
 * production safety. Requires a clean Git repo, committed locks and authenticated CLIs.
 * Keep this controller outside an agent's editable paths.
 */
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, join, resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const data = JSON.parse(readFileSync(join(root, 'docs/tasks.json'), 'utf8'));
const args = process.argv.slice(2);
const argValue = key => args.includes(key) ? args[args.indexOf(key) + 1] : null;
const taskId = argValue('--task');
const all = args.includes('--all');
const show = args.includes('--show') || (!taskId && !all);
const planOnly = args.includes('--architect');
const MAX_LOG = 250_000;
const frozen = ['AGENTS.template.md', 'CLAUDE.md', 'implementation.md', 'docs/tasks.json',
  'docs/traceability.csv', 'docs/security-invariants.md', 'docs/progress.json',
  '.github/', '.claude/', '.codex/', 'scripts/agent-runner.mjs',
  'scripts/bootstrap-agents.mjs', 'scripts/validate-repo.mjs', 'uv.lock',
  'apps/web/package-lock.json', 'package.json', 'pyproject.toml', 'learning.md',
  'docs/requirements/', 'scripts/dev.mjs', 'scripts/check-contract.mjs'];
const quoteArg = a => (/^[\w@%+=:,./\\-]+$/.test(a) ? a : `"${String(a).replaceAll('"', '\\"')}"`);
function run(command, argv, cwd = root, options = {}) {
  // options.shell: needed on Windows for npm/codex .cmd shims (Node refuses them otherwise).
  // Only fixed arguments and tracked docs/tasks.json gate strings are passed through the shell.
  const spawnArgs = options.shell
    ? [[command, ...argv.map(quoteArg)].join(' '), { shell: true }]
    : [command, argv, {}];
  const result = spawnSync(spawnArgs[0], ...(options.shell ? [] : [spawnArgs[1]]), {
    ...(options.shell ? spawnArgs[1] : {}),
    cwd, encoding: 'utf8', input: options.input, timeout: options.timeout ?? 60_000,
    maxBuffer: 32 * 1024 * 1024,
    env: { ...process.env, DO_NOT_TRACK: '1', ...options.env },
  });
  const output = [result.stdout, result.stderr].filter(Boolean).join('\n').slice(-MAX_LOG);
  if (options.log) writeFileSync(options.log, output);
  if (result.error || result.status !== 0) {
    throw new Error(`${command} ${argv.join(' ')}: exit ${result.status ?? 'N/A'}; ${String(result.error ?? '')} ${output.slice(-1800)}`);
  }
  return output.trimEnd();
}
const git = (cwd, ...args) => run('git', args, cwd);
function modified(cwd, base) {
  const tracked = git(cwd, 'diff', '--name-only', base, '--').split('\n').filter(Boolean);
  const newFiles = git(cwd, 'ls-files', '--others', '--exclude-standard').split('\n').filter(Boolean);
  return [...new Set([...tracked, ...newFiles])].sort();
}
function allowed(file, prefixes) {
  return prefixes.some(p => file === p || (p.endsWith('/') && file.startsWith(p)));
}
function checkChanges(wd, base, task) {
  if (git(wd, 'rev-parse', 'HEAD') !== base) throw new Error('Agent committed without runner approval');
  const changed = modified(wd, base);
  for (const file of changed) {
    if (frozen.some(p => file === p || (p.endsWith('/') && file.startsWith(p)))) throw new Error(`Protected file modified: ${file}`);
    if (file.endsWith('/AGENTS.template.md')) throw new Error(`Protected agent template modified: ${file}`);
    if (!allowed(file, task.allow)) throw new Error(`Out-of-task change: ${file}`);
    if (/\.(pem|p12|key)$/.test(file)) throw new Error(`Potential key material created: ${file}`);
    if (/(^|\/)(test_[^/]*\.py|[^/]*\.test\.[jt]sx?)$/.test(file)) {
      const existing = git(wd, 'ls-tree', '-r', '--name-only', base, '--', file);
      if (existing) throw new Error(`Protected existing test modified: ${file}`);
    }
  }
  return changed;
}
function codex(worktree, prompt, evidence, name, model, effort, review = false) {
  const file = join(evidence, `${name}.txt`);
  const commands = ['exec', ...(model ? ['--model', model] : []), '--sandbox', review ? 'read-only' : 'workspace-write',
    '--skip-git-repo-check', '-c', 'approval_policy=never', '-c', `model_reasoning_effort=${effort}`,
    '--output-last-message', file];
  if (review) commands.push('--output-schema', join(evidence, 'review-schema.json'));
  commands.push('-');
  run('codex', commands, worktree, { shell: true, input: prompt, timeout: data.policy.timeout_seconds * 1000, log: join(evidence, `${name}.log`) });
  return readFileSync(file, 'utf8');
}
function checkPrerequisites() {
  if (!existsSync(join(root, 'uv.lock')) || !existsSync(join(root, 'apps/web/package-lock.json')))
    throw new Error('Lockfiles missing; run uv lock && npm install --prefix apps/web, then commit both before using agents.');
  if (process.env.OPENAI_API_KEY || process.env.ANTHROPIC_API_KEY)
    throw new Error('API keys present; this harness is for subscription-based CLI authentication only.');
  if (git(root, 'status', '--porcelain'))
    throw new Error('Main Git working tree must be clean and lockfiles committed.');
  run('node', ['scripts/validate-repo.mjs'], root);
  // Agent instructions must be materialized, even when Git ignores them.
  run('node', ['scripts/bootstrap-agents.mjs'], root);
}
function currentState() {
  return JSON.parse(readFileSync(join(root, 'docs/progress.json'), 'utf8'));
}
function doTask(task) {
  const completed = currentState().completed;
  if (completed.includes(task.id)) return console.log(`SKIP ${task.id}: completed`);
  if (!task.depends_on.every(id => completed.includes(id))) throw new Error(`Missing prerequisites for ${task.id}`);
  checkPrerequisites();
  const base = git(root, 'rev-parse', 'HEAD');
  const branch = `agent/${task.id.toLowerCase()}-${base.slice(0, 8)}`;
  const scratch = mkdtempSync(join(tmpdir(), `datasoft-${task.id.toLowerCase()}-`));
  const wd = join(scratch, 'repo');
  const logs = join(root, '.agent_runs', task.id, base.slice(0, 8));
  mkdirSync(logs, { recursive: true });
  let attached = false;
  let gateEnv = null;
  let merged = false;
  try {
    run('git', ['worktree', 'add', '-b', branch, wd, base], root, { timeout: 60_000 });
    attached = true;
    run('node', ['scripts/bootstrap-agents.mjs'], wd);
    const usesDocker = task.gates.some(g => /\bdocker\b/.test(g));
    if (usesDocker) {
      cpSync(join(wd, '.env.example'), join(wd, '.env'));
      const project = `datasoft_${task.id.toLowerCase().replace('-', '')}_${base.slice(0, 6)}`;
      const ports = 19000 + data.tasks.findIndex(t => t.id === task.id) * 10;
      gateEnv = { COMPOSE_PROJECT_NAME: project, API_PUBLISHED_PORT: String(ports), ML_PUBLISHED_PORT: String(ports + 1), WEB_PUBLISHED_PORT: String(ports + 2) };
    }
    // Native setup: a fresh worktree has no .venv or node_modules (both gitignored).
    run('uv', ['sync', '--locked'], wd, { timeout: 600_000, log: join(logs, 'setup-uv.log') });
    run('npm', ['ci', '--prefix', 'apps/web', '--no-audit', '--no-fund', '--prefer-offline'], wd,
      { shell: true, timeout: 600_000, log: join(logs, 'setup-npm.log') });
    const promptBase = `Implement ONLY ${task.id}: ${task.title}. Requirement IDs: ${task.req.join(', ')}.\n` +
      `Read in order: AGENTS.md, learning.md (hard-won findings; follow them), the ${task.id} section of implementation.md, ` +
      `the matching requirement text in docs/requirements/qfd.md, docs/security-invariants.md, then only the code you need.\n` +
      `Paths allowed: ${task.allow.join(', ')}.\nAcceptance commands (run by the harness afterwards): ${task.gates.join(' ; ')}.\n` +
      `Environment: native Windows, no Docker. Run Django tests with \`node scripts/dev.mjs pytest -q services/api/tests\`, ` +
      `web checks with \`npm run --prefix apps/web check\`, lint with \`node scripts/dev.mjs lint\`, and after any API change ` +
      `regenerate the contract with \`node scripts/check-contract.mjs --write\` (never hand-edit contracts/ or generated/). ` +
      `If a command cannot run inside your sandbox (e.g. database access), still write the code and tests carefully; the harness runs the gates.\n` +
      `Write tests first, then implementation. Do not change existing tests, protected files, dependency locks, task definitions or policies. ` +
      `Do not add dependencies. Prefer TypeScript outside Django/FastAPI; use uv for all Python. ` +
      `Every UI action must call a real endpoint. Synthetic data only. Don't commit, never push. Output BLOCKED on uncertainty.\n`;
    let architecture = '';
    if (planOnly) {
      architecture = run('claude', ['-p', `Evaluate only ${task.id}: ${task.title}; read architecture/security docs, return concise advisory plan with no writes.`,
        '--model', 'opus', '--effort', 'medium', '--max-turns', '5', '--permission-mode', 'plan'], wd,
        { timeout: 500_000, log: join(logs, 'architecture.log') }).slice(-4_000);
    }
    const schema = { type: 'object', properties: {
      verdict: { type: 'string', enum: ['PASS','FAIL'] }, findings: { type: 'array', items: { type: 'string' } },
    }, required: ['verdict','findings'], additionalProperties: false };
    writeFileSync(join(logs, 'review-schema.json'), JSON.stringify(schema));
    let findings = [];
    let lastEvidence = [];
    let attemptsUsed = 0;
    let success = false;
    for (let attempt = 0; attempt <= data.policy.max_review_retries; attempt++) {
      const prompt = promptBase + `\nArchitecture guidance:\n${architecture}\n` +
        (attempt ? `\nThe previous attempt is still in the working tree. Fix ONLY these findings (do not weaken or delete tests):\n${findings.join('\n')}` : '');
      console.log(`CODER ${task.id} attempt ${attempt}`);
      codex(wd, prompt, logs, `coder-${attempt}`, process.env.DATASOFT_CODER_MODEL || null, 'high');
      const changed = checkChanges(wd, base, task);
      if (!changed.length) throw new Error('No source changes; cannot mark task implemented');
      const evidence = [];
      let gateFailure = null;
      for (let idx = 0; idx < task.gates.length; idx++) {
        const command = task.gates[idx];
        // Commands are from tracked docs/tasks.json, not agent-generated input.
        try {
          run(command, [], wd, {
            shell: true, timeout: data.policy.timeout_seconds * 1000, log: join(logs, `gate-${attempt}-${idx}.log`), env: gateEnv ?? {},
          });
          evidence.push(`${command}: EXIT 0`);
          console.log(`PASS ${task.id} ${command}`);
        } catch (error) {
          gateFailure = `Gate failed: ${command}\n${String(error.message).slice(-3000)}`;
          console.log(`FAIL ${task.id} ${command}`);
          break;
        }
      }
      if (gateFailure) {
        // Bounded: gate failures share the max_review_retries budget; then the task is BLOCKED.
        findings = [gateFailure];
        if (attempt === data.policy.max_review_retries) throw new Error(`Gate retry limit reached: ${gateFailure.slice(0, 1500)}`);
        continue;
      }
      checkChanges(wd, base, task);
      lastEvidence = evidence;
      attemptsUsed = attempt + 1;
      // Supply evidence and require reviewer to inspect actual Git diff itself.
      const reviewText = codex(wd, `Read-only review of ${task.id}. Base ${base}. Inspect git diff, changed files, new tests, security invariants and acceptance criteria.\nGates: ${evidence.join('\n')}\n` +
        `Check the requirement text in docs/requirements/qfd.md, the task section of implementation.md and the pitfalls in learning.md.\n` +
        `Look for tenant boundary leaks, invalid state changes, weak tests, privilege escalation, secrets, UI buttons not backed by real endpoints, and scope creep.\n` +
        `Only FAIL for real defects (correctness, security, missing acceptance criteria or tests); list minor suggestions as findings with a PASS verdict.\n` +
        `Return JSON verdict and findings only, FAIL when uncertain.`, logs, `review-${attempt}`,
        process.env.DATASOFT_REVIEWER_MODEL || null, task.phase === 1 || task.phase === 2 || task.phase >= 5 ? 'medium' : 'low', true);
      const review = JSON.parse(reviewText);
      writeFileSync(join(logs, `review-${attempt}.json`), JSON.stringify(review, null, 2));
      console.log(`REVIEW ${task.id} attempt ${attempt}: ${review.verdict}${review.findings?.length ? ` (${review.findings.length} findings)` : ''}`);
      if (review.verdict === 'PASS') { success = true; break; }
      findings = review.findings ?? [];
      if (attempt === data.policy.max_review_retries) throw new Error(`Reviewer retry limit reached: ${findings.join('; ')}`);
    }
    if (!success) throw new Error('No confirmed PASS');
    checkChanges(wd, base, task);
    const state = currentState();
    state.completed.push(task.id);
    state.latest_review = 'PASS';
    state.evidence = state.evidence ?? {};
    state.evidence[task.id] = { mode: 'native-windows', implemented_by: 'codex (agent-runner)', gates: lastEvidence, review: 'codex read-only PASS', attempts: attemptsUsed, base };
    state.last_updated = new Date().toISOString().slice(0, 10);
    writeFileSync(join(wd, 'docs/progress.json'), JSON.stringify(state, null, 2) + '\n');
    git(wd, 'add', '-A');
    // Owner is the sole author: local git identity, no Co-Authored-By or tool attribution.
    git(wd, 'commit', '-m', `feat(${task.id.toLowerCase()}): ${task.title.toLowerCase()}`);
    git(root, 'merge', '--ff-only', branch);
    merged = true;
    console.log(`PASS ${task.id}: locally merged. GitHub CI remains an independent gate.`);
  } finally {
    if (attached && gateEnv) {
      try { run('docker', ['compose', '-f', 'compose.yaml', 'down', '--remove-orphans', '-v'], wd, { timeout: 120_000, env: gateEnv }); }
      catch (e) { console.error(`Could not clean disposable containers: ${e.message.slice(0, 300)}`); }
    }
    if (attached) {
      try { run('git', ['worktree', 'remove', '--force', wd], root, { timeout: 300_000 }); }
      catch (e) { console.error(`Could not remove temporary worktree: ${e}`); }
      if (merged) {
        try { git(root, 'branch', '-d', branch); } catch { /* keep branch if not fully merged */ }
      }
    }
    // Keep evidence for debugging; no external log upload.
    console.log(`Evidence stored locally under ${logs}`);
  }
}
if (show) {
  const completed = currentState().completed;
  for (const t of data.tasks) {
    const state = completed.includes(t.id) ? 'DONE' : t.blocked_until ? 'HOLD' : 'TODO';
    console.log(`${state} ${t.id}: ${t.title}${t.blocked_until && state === 'HOLD' ? ` [${t.blocked_until}]` : ''}`);
  }
} else {
  // Tasks with blocked_until are owner-deferred: never selected by --all, refused by --task.
  const pending = data.tasks.filter(t => !currentState().completed.includes(t.id) && !t.blocked_until);
  const selection = all ? pending : data.tasks.filter(t => t.id === taskId);
  if (selection.length === 0) throw new Error(`Unknown or already-completed task ${taskId ?? ''}`);
  const held = selection.find(t => t.blocked_until);
  if (held) throw new Error(`${held.id} is on hold: ${held.blocked_until}`);
  if (selection.length > data.policy.max_tasks_per_run) throw new Error('Task cap exceeded');
  for (const task of selection) {
    try { doTask(task); }
    catch (error) { console.error(`BLOCKED ${task.id}: ${error.message}`); process.exit(1); }
  }
}
