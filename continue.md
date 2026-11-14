# continue.md — handoff for a new chat (written 2026-11-15)

Paste this into a new chat: **"Read continue.md and continue from where it left off."**

## 1. Your role and the owner's hard rules
- You are the **orchestrator**. You do not write product code yourself. **Claude Sonnet (medium effort) codes and reviews** through
  `scripts/agent-runner.mjs` (Codex usage is exhausted; `docs/tasks.json` `policy.coder = "claude"`, `policy.reviewer = "claude"`).
  You may fix orchestration and tooling (runner, scripts, docs, task notes).
- **The owner is the sole commit author.** Never add `Co-Authored-By` or "Generated with" lines. The runner commits with the local identity.
- **Never commit `CLAUDE.md`** (it stays in `.gitignore`). Never `git push`. Synthetic data only.
- Native **Windows + PowerShell, no WSL2, no Docker** for local dev. Git Bash is available for the Bash tool.
- Prototype first: features that work in the browser beat hardening. Reviews FAIL only on blocking defects; the rest goes to
  `docs/review-backlog.md`.
- **A UI task is not done until you have clicked through it in Chrome** (claude-in-chrome) as each affected role. Gates and
  reviews once passed while the UI was completely broken.
- Watch memory (16 GB laptop; background jobs were killed twice at low RAM). Run at most 2 tasks at once, stop the dev servers
  while runner tasks set up, and keep a free-RAM watchdog (warn below 1.5 GB).

## 2. Read these first
1. `learning.md`: every pitfall hit so far (environment, Windows, sandbox, DRF, TanStack, review loops, parallel merges). Follow it.
2. `prompt.md`: prompts and note patterns that worked.
3. `implementation.md` (plan; owner decisions inline), `docs/tasks.json` (task order, gates, policy), `docs/requirements/qfd.md` (requirements).
4. `docs/task-notes/P4-T3.md`: the spec for the task in progress.

## 3. Current state
- HEAD `0a08954` on `master`, tree clean. Done (runner `--show`): P0-T1, P0-T2, P1-T1, P1-T1b, P1-T2, P2-T1, P2-T2, P3-T1,
  P3-T2, P4-T1, P4-T2, P4-T2b. **P3-T3 (email) is on HOLD** until the owner sets up email (owner decision).
- Working and browser-verified: separate Client portal and DataSoft console; create/submit request; accept, assign, start,
  deliver, verify, close, reopen; user switching; comments; internal notes/tasks; notifications; reports and CSV.
  `scripts/smoke-lifecycle.mjs` passes 47 API checks.
- **In progress: P4-T3 "Usable attachments and professional visual design"** (owner complaint: "file uploads don't work",
  "the UI looks really ugly"). Sonnet stopped mid-task on a usage limit. Its partial work (14 files, unverified) is saved at
  `.agent_runs/seeds/P4-T3-0a089542.patch`. Findings (browser + API): basic upload/download works for both sides, but
  (a) the New request form has no attachment field, (b) .docx/.xlsx are rejected, (c) the UI shows only "Upload failed (400)"
  without the server message, (d) there is no dropzone, file list details or feedback. The whole UI needs a design system and a sidebar layout.

## 4. Next steps
1. Check free memory. Then resume P4-T3 from the saved work:
   ```
   node scripts/agent-runner.mjs --task P4-T3 --seed-patch .agent_runs/seeds/P4-T3-0a089542.patch --note-file docs/task-notes/P4-T3.md
   ```
   (If the patch no longer applies because HEAD moved, rebuild it on HEAD: apply at its base `0a08954`, commit, rebase, resolve.
   See learning.md §7.) Monitor `.agent_runs/p4-t3-run.log` for CODER/GENERATED/PASS/FAIL/REVIEW/SAVED/BLOCKED lines.
2. After it merges: `node scripts/dev.mjs migrate`, start `node scripts/dev.mjs` (Django :8000 + Vite :5173), and verify in
   Chrome: attach files on New request (png/jpg/pdf/docx/xlsx), see the real error for a bad type, the dropzone/file list/thumbnails,
   comment attachments, and download as a bank user and as DataSoft. Check that the new look (sidebar, tokens, components) is
   applied on login, dashboards, list, detail and form for both experiences, and at a narrow width. Record any defects as a
   follow-up task note (`docs/task-notes/P4-T3b.md` plus a tasks.json entry) and run it the same way.
3. Then ask the owner whether to do: the hardening pass (`docs/review-backlog.md`), the optional P5-T1/P5-T2 (ML duplicate
   detection/labels; "do not start until the core is reliable"), or P6-T1 (audit hash chain + backup drill).

## 5. Handy facts
- Demo users (synthetic, from `node scripts/dev.mjs seed`), password `Demo-Pass-2026!`: `ds.admin`, `ds.support`,
  `ds.support2`, `nwd.officer`, `nwd.verifier`, `nwd.dual`, `rsd.officer`, `rsd.verifier`.
- Commands: `node scripts/dev.mjs [all|api|web|migrate|seed|test|lint|pytest ...|manage ...]`,
  `node scripts/check-contract.mjs [--write]`, `node scripts/agent-runner.mjs --show | --task <ID> [--seed-patch F] [--note-file F] [--skip-coder] | --integrate <ID> --branch <b>`.
- PostgreSQL 18 + pgvector is installed natively (`C:\Program Files\PostgreSQL\18`); dev DB `datasoft` (role `datasoft`); defaults live in `scripts/dev.mjs`.
- If a runner task is blocked, the runner saves `.agent_runs/seeds/<task>-<base>.patch`. Resume with `--seed-patch` plus a note
  explaining what failed. Never ask a coder to edit an existing test file (the harness blocks it); ask for new test files.
- If `npm ci`/`vite` fails in the main checkout (`node_modules/.bin` emptied), run `npm ci --prefix apps/web`.
