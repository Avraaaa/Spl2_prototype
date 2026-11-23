# Progress — resume here

Last updated: 2026-11-24 04:00 (local).  Owner: sole author of every commit (no co-author trailers).
Next session: read this file, then `learning.md`, then continue at **Next steps**.

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
| P8-T2 | Admin audit log viewer `/admin/audit` (filters, CSV, chain-integrity banner) | merged c41de37; **not yet verified in browser** |

Key data files: `.agent_runs/compare-790.json` (before), `.agent_runs/compare-790-p7t15.json` (current baseline), `.agent_runs/synthetic-manifest.json`.

Current baseline (790 synthetic requests): duplicate hit@5 lexical 0.738 / dense **0.917** / hybrid 0.877; hard-negative FP@5 dense 0.31; labels acc@1 0.972; topic purity 0.073; masking P 1.00 / R 0.89.

## State at end of session
- **P9-T1 merged** (score-based fusion + `--fusion-alphas` sweep). Its defaults (0.85 / 0.95 Bangla) are NOT tuned yet: see Next step 2.
- **P8-T3 BLOCKED** after 3 retries, for a trivial reason: its new test file uses a non-existent fixture `client_for`. Feature code passed all other gates and the 339 existing tests. Seed patch: `.agent_runs/seeds/P8-T3-a62444ad.patch`; note: `docs/task-notes/P8-T3-resume.md`.
- No runner or dev server is running.

## Next steps (in order)
1. Resume P8-T3: `POSTGRES_TEST_DB=test_datasoft_p8t3 DATASOFT_CODER=codex DATASOFT_CODER_MODEL=gpt-6-luna DATASOFT_CODER_EFFORT=medium DATASOFT_RETRY_EFFORT=medium node scripts/agent-runner.mjs --task P8-T3 --seed-patch .agent_runs/seeds/P8-T3-a62444ad.patch --note-file docs/task-notes/P8-T3-resume.md`
2. **P9-T1 follow-up:** run `node scripts/dev.mjs manage compare_features --manifest .agent_runs/synthetic-manifest.json --output .agent_runs/compare-790-fusion.json --fusion-alphas "0.5,0.6,0.7,0.8,0.85,0.9,0.95,1.0"` (about 15 min). Set `SEARCH_FUSION_ALPHA` / `SEARCH_FUSION_ALPHA_BANGLA` defaults from the **tune-half** best and report holdout numbers. Hybrid must beat dense (0.917).
3. Run **P8-T4** (sub-stages inside the locked lifecycle + drag-and-drop request board `/board`, admin `/admin/stages`) and **P8-T5** (analytics `/analytics`, metrics researched from Jira SM, Zendesk/Freshdesk and Kanban tools, inline SVG charts) **in parallel**. Both depend on P8-T3. They are already defined in `docs/tasks.json` with anchors in App.tsx, nav.ts and AdminFrame.tsx.
4. **Browser verification** (`node scripts/dev.mjs`, demo password in `seed_demo.py`): label suggestions appear on the officer's new-request form (proves P7-T16 + the dev wiring); Kanban drag-and-drop as `ds.support`; audit log + colours as `ds.admin`; then the board and analytics once merged. Bank users must not see other banks or internal stage names.
5. **Polish task** from review follow-ups (`docs/review-backlog.md`, P7-T16/P8-T1/P8-T2 sections): audit log pagination (capped at 500 today) and verify_chain once per request; Kanban long JSX lines, drag handle, no-op drop, hover highlight; ML failed-load caching and a lock.
6. **ML improvements** (owner asked; research in `papers/NOTES.md`, 13 PDFs, gitignored):
   a. done as P9-T1 (fusion);
   b. benchmark `intfloat/multilingual-e5-base`, then `BAAI/bge-m3`. **Ask the owner before downloading any model** (state files and sizes);
   c. bge-m3 sparse head instead of Postgres FTS for Bangla (lexical hit@5 only 0.35);
   d. cross-encoder rerank of the top 10-20 for hard negatives (31% FP);
   e. UMAP before HDBSCAN for topic clustering (purity 0.07).
   Each change must beat `.agent_runs/compare-790-p7t15.json` on the same data.
7. Small fixes: Bangla account numbers next to an NID are masked as `[NID]` instead of `[ACCOUNT_NUMBER]` (still hidden, wrong type); OTP after the generic word "code" is missed (acceptable).
8. **EX-09:** run `node scripts/backup-restore-drill.mjs` once and keep the evidence. The QFD requires the backup and restore to be demonstrated, and no run record exists yet.
9. Update `docs/traceability.csv` for the new P8/P9 tests when they merge.

## Owner decisions (2026-11-24)
- Custom workflow = **admin-defined sub-stages inside the locked QFD lifecycle** (statuses and transitions unchanged).
- Custom colours for **all**: labels, request types, statuses/stages, products.
- Parallel tasks are wanted; Claude acts as supervisor ensuring the QFD works end to end.
- Papers may be downloaded into `papers/` (gitignored). Model downloads still need a yes with sizes.
