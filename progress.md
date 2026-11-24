# Progress — resume here

Last updated: 2026-11-24 10:15 BST.  Owner: sole author of every commit (no co-author trailers).
Next session: read this file, then `learning.md`, then continue at **Next steps**.

## Roles (who does what)
- **You, the AI reading this file (Claude Code, main session) = supervisor/orchestrator.** You do NOT write product code. You:
  pick the next task, write its entry in `docs/tasks.json` + `implementation.md` (+ a note in `docs/task-notes/` if needed),
  launch coders through the runner, watch the logs, diagnose failures, resume blocked tasks, run measurements
  (`compare_features`, test suites), verify features yourself in the browser (Claude in Chrome) as each role,
  update `docs/traceability.csv`, `learning.md` and this file, and commit docs/config as the owner (no AI attribution).
  You may edit only files the runner freezes for coders (tasks.json, implementation.md, traceability.csv, learning.md,
  scripts/dev.mjs, docs/task-notes/, progress.md) and anchor comments that coordinate parallel tasks.
- **Coder = Codex `gpt-6-luna`, medium effort**, launched only via `scripts/agent-runner.mjs`, one task per call, at most 2 in parallel.
  It writes code and new tests; it cannot run Python in its sandbox; the runner runs the gates.
- **Reviewer = Claude Sonnet, medium effort**, run automatically by the runner (read-only). It fails only on blocking defects;
  everything else goes to `docs/review-backlog.md` as follow-ups.
- **Research / side jobs = a Sonnet subagent at low effort** (or luna at medium), e.g. the paper study in `papers/NOTES.md`.
- **Opus**: only for phase architecture or a real blocker, sparingly.
- **Owner (human)**: makes product decisions, approves model downloads and anything outward-facing; is sole Git author.

## How work is done
- Claude orchestrates and verifies; **luna (Codex `gpt-6-luna`, medium effort)** writes code through the runner:
  `DATASOFT_CODER=codex DATASOFT_CODER_MODEL=gpt-6-luna DATASOFT_CODER_EFFORT=medium DATASOFT_RETRY_EFFORT=medium POSTGRES_TEST_DB=test_datasoft_<task> node scripts/agent-runner.mjs --task <ID>`
- At most **2 runner tasks in parallel**, each with its own `POSTGRES_TEST_DB`. Stop dev servers before running tasks (memory).
- Do not commit to master while a runner is between its rebase and merge (`[rebased]` lines in its log).
- Research/side jobs: Sonnet at low effort, or luna at medium.
- Resume an interrupted task: `node scripts/agent-runner.mjs --task <ID> --seed-patch .agent_runs/seeds/<file>.patch` (add `--skip-coder` to re-gate only).

## Done this session (all merged on master, all gates green)
| Task | What | Evidence |
|---|---|---|
| P7-T15 | Masking detector fixes (phones/accounts no longer swallowed by the card rule; Txn ID, E-xxxx and SR-xxxx no longer masked; Bangla/Banglish formats) | 790-run: masking precision 0.62→**1.00**, recall 0.61→**0.89**, altered must-not-mask 41→**0**; checked in browser |
| — | `docs/traceability.csv`: all 55 requirements mapped to real tests, status `TESTED@7aae40e` | full suites passed: 339 API, 6 ML, 62 web |
| — | `scripts/dev.mjs`: `node scripts/dev.mjs` now starts API + web + **ML (8001)** and wires the API to it (`ML_SERVICE_URL`, token); tests stay hermetic | commit 1bb1aed |
| P7-T16 | ML service loads the model once and preloads it at startup (it used to reload per request, 4-17 s, so the app silently ran lexical-only) | merged 1d4d654; **not yet verified in browser** |
| P8-T1 | Drag-and-drop Kanban for internal tasks (native HTML5 DnD, optimistic update + rollback, filters) | merged 1f6f32e; **not yet verified in browser** |
| P9-T1 | Hybrid search fuses normalised scores (alpha*dense + (1-alpha)*lexical, separate alpha for Bangla script) instead of reciprocal rank; compare_features gains a held-out alpha sweep | merged; alpha not tuned yet |
| P8-T3 | Custom colours for labels, request types, statuses, products (admin `/admin/colors`) | merged 9ed12b9; **not yet verified in browser** |
| P8-T2 | Admin audit log viewer `/admin/audit` (filters, CSV, chain-integrity banner) | merged c41de37; **not yet verified in browser** |

Key data files: `.agent_runs/compare-790.json` (before), `.agent_runs/compare-790-p7t15.json` (current baseline), `.agent_runs/synthetic-manifest.json`.

Current baseline (790 synthetic requests): duplicate hit@5 lexical 0.738 / dense **0.917** / hybrid 0.877; hard-negative FP@5 dense 0.31; labels acc@1 0.972; topic purity 0.073; masking P 1.00 / R 0.89.

## State at end of session (2026-11-24 ~10:15 BST)
- **Master is runnable**: P8-T3 (custom colours) merged as 9ed12b9, all gates green (validate, makemigrations, contract, lint, full tests, review PASS with 5 follow-ups). `node scripts/dev.mjs` starts it.
- **P8-T4 and P8-T5 were launched in parallel at 04:06Z** (logs `.agent_runs/logs/p8t4.log`, `p8t5.log`; test DBs test_datasoft_p8t4 / _p8t5). The runner merges only after all gates pass, so master stays runnable whatever happens. If the session died mid-run, check the logs: a DONE/PASS "locally merged" line means it landed; otherwise resume with a seed patch from `.agent_runs/seeds/` (or rerun the task). Delete any leftover empty `agent/p8-t4-*`/`agent/p8-t5-*` branch first (`git log master..<branch>` empty), or the runner fails with "branch already exists".
- **Fusion alpha sweep was stopped** (crawled at 0.03 req/s while coders ran; only 150/790). Rerun it alone with nothing else running (see Next step 2).
- Learned: a seed patch goes stale when master changes; rebase it with `git apply --3way` in a temp worktree, resolve, re-export (done for P8-T3: `.agent_runs/seeds/P8-T3-rebased.patch`).

## Next steps (in order)
1. Check P8-T4 / P8-T5 outcome (see above). Then update `docs/traceability.csv` for P8-T3/T4/T5 tests.
2. **P9-T1 follow-up:** with no runner active, run `node scripts/dev.mjs manage compare_features --manifest .agent_runs/synthetic-manifest.json --output .agent_runs/compare-790-fusion.json --fusion-alphas "0.5,0.6,0.7,0.8,0.85,0.9,0.95,1.0"` (~45 min alone). Set `SEARCH_FUSION_ALPHA` / `SEARCH_FUSION_ALPHA_BANGLA` from the tune-half best; hybrid must beat dense (0.917) on holdout.
3. **Browser verification** (`node scripts/dev.mjs`, demo password in `seed_demo.py`): label suggestions on the officer new-request form (P7-T16); Kanban DnD as ds.support (P8-T1); audit log (P8-T2) + colours (P8-T3) as ds.admin; board + analytics once merged. Bank users must not see other banks or internal stage names.
4. **Polish task** from `docs/review-backlog.md` (P7-T16/P8-T1/P8-T2/P8-T3 sections): audit-log pagination (500 cap), verify_chain once per request, Kanban drag handle/no-op drop/hover, ML failed-load caching + lock.
5. **ML improvements** (papers/NOTES.md): b. benchmark multilingual-e5-base then bge-m3 (**ask owner before downloading, give sizes**); c. bge-m3 sparse for Bangla lexical; d. cross-encoder rerank top 10-20; e. UMAP before HDBSCAN. Each must beat `.agent_runs/compare-790-p7t15.json`.
6. Small fixes: Bangla account number next to NID masked as [NID]; OTP after "code" missed (acceptable).
7. **EX-09:** run `node scripts/backup-restore-drill.mjs` once and keep the evidence.

## Owner decisions (2026-11-24)
- Custom workflow = **admin-defined sub-stages inside the locked QFD lifecycle** (statuses and transitions unchanged).
- Custom colours for **all**: labels, request types, statuses/stages, products.
- Parallel tasks are wanted; Claude acts as supervisor ensuring the QFD works end to end.
- Papers may be downloaded into `papers/` (gitignored). Model downloads still need a yes with sizes.
