# Exact local orchestrator flow

The runner's task execution is deterministic; the LLMs do not grant themselves
permissions. From the repository root (on a disposable Linux/WSL2 machine):

```sh
claude --version
codex --version
claude /login  # interactive only if not signed in
codex login    # interactive only if not signed in
node scripts/bootstrap-agents.mjs
uv lock && uv sync --locked
npm install --prefix apps/web --no-audit --no-fund
git init && git add -A && git commit -m 'chore: initialize safe skeleton' 
node scripts/agent-runner.mjs --show
node scripts/agent-runner.mjs --task P0-T1 --architect
node scripts/agent-runner.mjs --task P0-T2
# Only after validating the harness and workload, optionally:
node scripts/agent-runner.mjs --all
```

* `--architect`: runs `claude -p --model opus --effort medium --max-turns 5 --permission-mode plan` once, from a disposable worktree, and includes bounded advice in the Codex prompt. Prefer one Opus call per phase, not every task, to conserve Claude Pro allowance.
* Coder: `codex exec --model gpt-6-luna --sandbox workspace-write -c approval_policy=never -c model_reasoning_effort=high --output-last-message PATH -` with task prompt on stdin.
* Controller rejects protected-file edits, out-of-scope changes, changes to previously tracked tests, agent-created commits, and any nonzero gate status.
* Reviewer: `codex exec --model gpt-6.1-sol --sandbox read-only -c approval_policy=never -c model_reasoning_effort=medium --output-schema SCHEMA --output-last-message PATH -` (low outside high-risk phases). Emits PASS/FAIL and findings; max two fix attempts.
* On PASS, controller updates `docs/progress.json` and creates one commit on the worktree branch, then fast-forward merges **locally only**. GitHub Actions tests the committed changes when a human elects to push.
* On FAIL, stop and preserve evidence path; never auto-promote, silently skip tests, retry indefinitely, switch to API billing, or create a deployment.

**Trust limit:** `--sandbox workspace-write` is a CLI-level software sandbox, not a guarantee that model-written commands cannot attack a developer host. In particular Docker socket access can confer host-level control. Run agent tools in a disposable VM with no Docker socket, external credentials or bank data; run privileged integration gates on an isolated runner, not in the agent's own environment. The included runner is an educational starting point, not an independently hardened security controller.

**Common source-of-truth:** Tracked `AGENTS.template.md` files generate ignored root and nested `AGENTS.md` files in every worktree. Codex reads them, while CLAUDE.md imports `@AGENTS.md`. Claude Code recently added direct AGENTS.md support when CLAUDE.md is absent. Do not turn on a duplicate-loading configuration; imported file content counts toward context. Keep always-loaded instructions <200 lines, put deep detail in docs.
