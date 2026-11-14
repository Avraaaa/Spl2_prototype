# prompt.md — prompts that worked (and why)

Maintained by the orchestrator. Companion to `learning.md` (which records pitfalls). Coder agents
should not edit this file. Ready-to-use per-task notes live in `docs/task-notes/<TASK>.md` and are
passed with `node scripts/agent-runner.mjs --task <ID> --note-file docs/task-notes/<ID>.md`.

## 1. The runner's base coder prompt (`scripts/agent-runner.mjs`, `promptBase`)
Structure that works:
1. **One task only**: `Implement ONLY <ID>: <title>. Requirement IDs: ...`
2. **Read order**: AGENTS.md → learning.md → the task section of implementation.md → the matching QFD text → security invariants → only the code needed.
3. **Allowed paths** and the gate commands the harness will run.
4. **Environment truth, stated bluntly**: the sandbox cannot run Python, so never run uv/python/pytest/manage.py/dev.mjs/check-contract (a failed attempt corrupts `.venv`). The harness formats, regenerates the contract and runs the gates. Name the generated type conventions so the frontend can be written before regeneration.
5. Tests first, no dependency changes, no edits to existing tests or policies, real endpoints behind every button, synthetic data, no commits, BLOCKED when uncertain.

Why: before item 4 was explicit, Codex spent attempts trying to run Python, deleted files in `.venv`, and failed lint repeatedly.

## 2. Task notes (`--note` / `--note-file`) — the biggest quality lever
What made a note work, so that gates passed on the first or second attempt:
- **List the concrete QFD fields and rules** (types, statuses, who may do what, what is invisible to whom), not just requirement IDs.
- **Name the existing helpers to reuse** (e.g. `authorized_rows`, `get_authorized_object_or_404`) and the rules for using them.
- **Name the lint rules that tripped earlier tasks** (ruff UP047/UP049 → PEP 695 generics without underscore).
- **Say which shared files to avoid** when tasks run in parallel (`tests/conftest.py`, `config/settings.py`, `config/urls.py`).
- **State what is out of scope** (e.g. "attachments are P3-T1", "transitions beyond submit are P2-T2") to prevent scope creep and timeouts.
- **Order the work** for big tasks: "finish backend wiring first, then frontend". The first P2-T1 attempt timed out with no API or UI because it did everything in parallel.

### Examples that worked
**P1-T2 (passed all gates on attempt 0 and the review first time):**
> A previous run of this task passed migrations, contract and tests but was lost on formatting only. Its design: services/api/domains/tenants/selectors.py with a shared authorized_rows(user, queryset, ...) selector and get_authorized_object_or_404(user, rows, pk) object policy (404 for other-bank objects, never revealing existence); tighten account permissions against mismatched memberships; two-bank isolation tests in services/api/tests/test_ex_02.py (guessed org/user IDs, header/query/body spoofing, cross-tenant selectors). Ruff rules that tripped it: UP047/UP049 - use PEP 695 generics with NO leading underscore ... Do not touch tests/conftest.py unless essential (parallel task P1-T1b also edits accounts code).

**P1-T1b (passing a prior review finding forward fixed it in one attempt):**
> Previous independent review FAILED only on: the username-change endpoint (and likewise the existing change-password endpoint ...) verify current_password without rate limiting ... Add a per-user throttle (own scope, rate in settings) to BOTH endpoints and tests proving repeated wrong-password attempts return 429. Everything else already passed all gates; keep it.

**P2-T1 resume (seeded, finished the remaining work, all gates passed on attempt 0):**
> Resume: the seeded work is a near-complete implementation (...list of what exists...). Earlier gate failures were caused by a corrupted .venv (environment, not your code); the harness now rebuilds it. Review the seeded code against N-05..N-08, N-10, N-11 and the plan; fix real gaps only; keep tests. Do NOT run uv/python/... in your sandbox.

Pattern: **tell the coder what already exists, what is verified, and exactly what is left.** Without that it re-plans from scratch.

## 3. Review prompt (read-only Codex, JSON verdict)
Worked well:
- "Inspect the git diff yourself" plus the gate evidence; check the QFD text, the plan section and learning.md.
- An explicit hunt list: tenant leaks, invalid state changes, weak tests, privilege escalation, secrets, **UI buttons not backed by endpoints**, scope creep.
- **"Only FAIL for real defects; put minor suggestions in findings with a PASS verdict."** Before this line, reviews could fail on style.
Findings it produced were real every time: logout state, temp-credential expiry, CSRF tests, password-check throttling, email length 254, masking gaps (OTP phrasing, dotted card numbers).

## 4. Resume prompts after failures
- Save the work: `git add -N <new>; git diff --binary HEAD > .agent_runs/seeds/<task>.patch` (the runner also does this automatically when a task is not merged).
- Relaunch: `--seed-patch <file> --note "<what exists / what failed and why / what is left>"`.
- If a failure was environmental (venv, timeout), **say so in the note** so the coder does not "fix" good code.

## 5. Effort settings
- First attempt: `high` (design work). Retries: `medium` (`DATASOFT_RETRY_EFFORT`), since they fix specific findings. Review: `medium` for phases 1, 2 and 5+, `low` otherwise.

## 6. Scope boundaries for reviewers
Add to the task section of `implementation.md`, and repeat in the note:
> Scope boundary: X is implemented in <later task> ... reviewers must not fail <task> for its absence.
The review prompt includes "Respect the scope boundaries in implementation.md" and the orchestrator note. Without that, the P2-T1 review failed for attachments planned for P3-T1.

## 7. Break a review loop with a design note
When reviews keep finding one more case of the same kind (e.g. a new OTP phrasing every round), stop the run and give the coder a
**design** plus a **must / must-not test table** instead of another patch request (`docs/task-notes/P2-T1-masking.md`).

## 8. Review severity for a prototype
The review prompt defines **blocking** (FAIL) vs **[follow-up]** (PASS and backlog). This turned "fix every edge case before merging"
into "ship working features, harden later". Follow-ups land in `docs/review-backlog.md` for a dedicated hardening task.

## 9. UI tasks: give the coder the browser-reproduced defect list
A note listing each defect with its exact cause (file, line, why), followed by a concrete UX spec per role (nav items,
dashboard lists, detail layout, guards) and a quality bar (readable JSX, shared components, loading/empty/error states), works
far better than "build the UI for N-xx". See `docs/task-notes/P4-T2.md`. Afterwards the orchestrator verifies in the browser.
