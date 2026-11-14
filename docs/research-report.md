# DataSoft agent-ready prototype: evidence-based architecture and implementation research

**Research date:** 2026-11-14. **Status:** architecture research + executable skeleton *infrastructure*, not a completed portal and not approved for a bank production network. **Primary source:** `DataSoft_QFD_General_Requirements5 (3).docx`, supplied by the project owner. All 55 identifiers N-01–N-26, EX-01–EX-11 and E-01–E-18 map to `traceability.csv` and `tasks.json`.

## Executive decision

One Git monorepo containing React 19 + TypeScript/Vite frontend; Django 6 + Django REST Framework as the *single* transactional authority; PostgreSQL 18 + pgvector; a small isolated FastAPI service for offline NLP; a PostgreSQL transactional outbox worker; and Python-led noninteractive Codex execution. Claude Code is an optional expensive phase-design and adversarial architectural adviser, not a model kept running for every edit. The `implementation.md` and checked-in tests define acceptance; the runner independently checks file scope and command exit statuses. Every automated change is local and gated; **production, client credentials, real email and real bank data require human approval**.

## Product domain invariants derived from DataSoft's requirements

- Each ticket belongs to exactly one client organization. `Issue Officer` creates drafts and authorizes submission *at submission*; there is no separate bank internal approval stage (N-10).
- `Issue Verifier` confirms or fails a delivered fix. One human may have both client roles (N-03). A `Support Agent` processes issues; only the `Administrator` creates/manages accounts and banks (N-01–N-04).
- State flow: Draft → Submitted → Accepted or Rejected; Accepted → Pending → In Progress → Delivered → Awaiting Verification → Verified → Closed. Verification failure is a historical event and returns to In Progress. Only DataSoft closes (N-12–N-19, EX-07).
- Reopening within 30 days of closure is permitted and the duration is configurable by Administrator; otherwise create a linked Recurring request. An unsuccessful verification never silently closes a ticket (N-11, N-19–20).
- The date *acceptance promise* differs from actual delivery date, submission date, last status update and closure date; preserve all of them in history (N-12, N-16, N-24).
- Tenant isolation applies to everything: attachments, reports, notifications, search, masked text, vectors, backup restore. Internal DataSoft notes and tasks are excluded from client serializers (EX-01–03).
- Full card numbers and OTP values must not be retained raw; ML inputs must be masked and may never leave DataSoft by default (E-11–15). Pattern masking will miss some personal details: human review and constrained original-value permissions are requirements, not optional polish.
- Immutable chronological actions are separate from a hash-chained verification ledger. The latter needs anchoring outside the database or an all-powerful DBA can rewrite and recompute the whole chain (EX-06, E-16–18).

## Specific technology decisions and rejected alternatives

| Question | Choice | Rationale and considered/rejected alternative |
|---|---|---|
| Backend authority | **Django + DRF** | Django authentication/admin/ORM/migrations/transactions fit workflow and multitenant permissions. FastAPI-only would contradict requirement Django use and duplicate business layers. Django Ninja is viable but DRF's ecosystem, permission/test patterns, and `drf-spectacular` OpenAPI fit this product better. |
| ML boundary | **FastAPI offline, optional** | Use Sentence-Transformers for embeddings; return suggestions only, never change ticket status directly. Direct embedding in Django would tie inference memory/availability to core requests. Full independent ML database writes rejected: consistency and tenancy harder. |
| React | **Vite + React Router + TanStack Query** | Lightweight bundling, declarative routes, server-state caching. No Next.js SSR needs; generated API types from drf-spectacular via `openapi-typescript` + `openapi-fetch`. TypeScript `strict` enabled. |
| Styling | **Plain CSS first** | Minimum runtime/build dependencies. Design system or Tailwind can be added with documented ADR if feature work proves it useful; avoid multiple UI kits and abandoned components. |
| Background jobs | **PostgreSQL transactional outbox with separate Django worker** | Ensures a workflow change and notification intent commit together; worker claims jobs with `FOR UPDATE SKIP LOCKED`, per-message idempotency, lease timeout, retry-with-backoff and dead-letter state. Redis/Celery rejected for this small prototype because a second broker adds operations; switch if throughput, scheduling, or orchestration justifies it. Django 6 Tasks API alone does *not* execute queued work: production needs an actual backend/worker. See Django Tasks documentation. |
| Email | **Django SMTP with outbox; console sink for demo** | Never inline email sending inside a ticket transaction. Mailpit could be a development profile later; don't send demo messages to actual banks. |
| Permissions | **Default deny, shared selectors and service actions, PostgreSQL RLS as defense in depth later** | All user tenant identities must come from authenticated membership, never user-controlled bank IDs. For a shared-table PostgreSQL layout, evaluate transaction-local RLS on every tenant table as a mandatory deployment hardening gate; application scoping cannot be the sole long-term assurance. RLS must not use superuser/BYPASSRLS role for tenant requests. |
| Search | **Postgres FTS/trigram + pgvector + RRF** | Exact fault codes and meaning complement each other. Use date/product narrowing and same-bank filter *inside candidate selection*. Do not automatically merge suggestions; users confirm. |
| Embeddings | **Local multilingual E5 small candidate, benchmark before approval** | Compare against BGE M3 offline; use `SentenceTransformer(..., local_files_only=True)` with pinned checksum; no download at runtime. Do not pretend multilingual benchmarks guarantee Bangla banking-domain performance. |
| Tests | **pytest-django, Vitest, Playwright at first end-to-end phase** | Require PostgreSQL-based concurrency tests and cross-bank negative tests. Playwright can be deferred until browser screens exist; don't claim E2E coverage from a health check. |
| Coding rules | **Ruff, mypy, ESLint, Prettier, TS strict, pre-commit, CI** | Enforce with machines; not merely AGENTS prose. Use import-linter/architectural contract check only when package boundaries become large enough to justify the extra dependency. |
| Operations | **Docker Compose dev; reviewed deployment later** | Keep development one command, database volume, profile for worker. Separate `compose.prod.yaml` is a topology sample, **not** full deployment (TLS/proxy, registry, monitoring, secrets and backups remain deployment decisions). |
| Audit | **Append-only event store + hash chain + verifier + external hash checkpoints** | Hash chaining detects modifications under limited threats. A checksum stored in the same mutable DB can be rewritten; periodic signed/checkpointed anchor outside DB is needed for meaningful DBA-level tamper evidence. |

### Data schema and concurrency design

Representative core tables: `Organization`, `User`, `Membership`, `Product`, `ProductModule`, `Ticket`, `TicketEvent`, `TicketRelation`, `TicketComment`, `InternalTask`, `Attachment`, `OutboxMessage`, `Notification`, `Embedding`, `AuditEvent`, `AuditAnchor`. Every tenant-owned record has an immutable organization foreign key. `Ticket` has `version` for an `If-Match` / expected-version check. Mutating endpoints call one action service inside `transaction.atomic`; action reads a locked ticket (`select_for_update`), verifies actor/status/organization, writes event and ticket version and outbox message in the *same* transaction. Report selectors never begin from an unscoped queryset for a bank user.

For the shared database, enforce a composite ownership invariant where possible (a comment's tenant must match its ticket). Validate foreign key ownership in application and add PostgreSQL constraints or triggers when the domain is implemented. No raw attachments in a public media directory; authenticated authorization must precede streaming or issuing a short-lived object-storage URL. Set upload size/type limits and malware scanning workflow according to bank risk policy.

### Why the transactional outbox matters

Without an outbox, a ticket may commit successfully and then its notification fail. With the outbox, `TicketEvent` and `OutboxMessage` enter the same PostgreSQL transaction; independent worker delivery can retry after a crash. Exactly-once external email delivery is generally impractical; implement **at-least-once** processing and deduplicate using stable event IDs. Test an SMTP timeout and worker restart with no lost notification intent. Django 6's Tasks API is a high-level task abstraction, not a ready-made worker implementation.

## Repositories evaluated

| Source | Directly useful conventions | Applicability verdict |
|---|---|---|
| [cookiecutter-django](https://github.com/cookiecutter/cookiecutter-django) | Python/Django layout, `.env`, migration discipline, Compose, pre-commit, hardened settings | Strong main app reference, but template is more infrastructure-heavy than needed. Its current project version on 2026-11-14 is 2026.11.6 on `main` (GitHub metadata; releases list can lag). |
| [HackSoftware/Django-Styleguide](https://github.com/HackSoftware/Django-Styleguide) | `services.py` for writes, `selectors.py` for reads, keep business logic out of serializers and views | Best domain-level convention; adapt rather than copy every recommendation. |
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | React/Vite/TS, generated OpenAPI client, Compose, pytest, Playwright, CI | Borrow frontend+integration patterns, **not** backend framework choice. |
| [alan2207/bulletproof-react](https://github.com/alan2207/bulletproof-react) | Feature folders, dependency/import boundaries, co-located tests, API layering | Useful educational guide, not an exact Django starter or turnkey production template. |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | Agent instruction handling, skills, hooks and native instruction behavior | Follow official published Claude Code docs for actual behavior. |
| [netbox-community/netbox](https://github.com/netbox-community/netbox) | Real-world repo agent/docs instructions where present; repository hygiene and developer notes | Exemplar of mature Django engineering rather than fork candidate. |

A single widely used Django+React+FastAPI+pgvector monorepo matching your exact requirements was not established by the references. Combining validated conventions creates a smaller, controlled foundation than adapting an unrelated fully built product.

## Agent instruction architecture and token economy

- **Single authority**: root `AGENTS.md` contains universal repository behavior, invariants, safe commands, task policy and pointers. `CLAUDE.md` contains `@AGENTS.md` as an import and minimal Claude-specific hint, not a copy.
- **Nested AGENTS** in `services/api`, `services/ml`, `apps/web` and `infra` contain only local boundaries and test commands, no duplicated root policy. Claude Code can load AGENTS natively in recent versions, but when CLAUDE.md exists it takes precedence unless imported. Import is compatible with Windows (unlike symlink workflows).
- **Always-loaded instructions**: target <=200 lines root; correctness and stop rules; commands to discover task docs. **On-demand docs**: architecture, security invariants, requirement-to-code traceability, ADR, task plan, state. Large lists of specs do not belong in every agent prompt.
- **Progressive disclosure**: pick one task by ID, give actor/requirements/allowed paths/commands, inspect relevant selectors and tests, not whole repository; report outputs and evidence paths. Replace verbose conversation summaries with `docs/progress.json` and immutable Git commits.
- **Caching**: static prefix instructions and stable code maps improve cache opportunity when vendor APIs implement caching, but subscription CLI caching controls vary. Avoid making quantitative cache-savings claims without measurements. Use small tasks and model selection to minimize quota use.
- **Anti-patterns**: enormous instructions copied into multiple files; contradictory rules; unconditional recursive repo reads; agents claiming tests passed without running them; prompting a reviewer to approve its own code; granting agents `danger-full-access`; exposing production secrets as context.

## Claude Code / Codex integration — what actually works

**Current official Codex tool**: `codex exec`, including `--model`, `--sandbox`, `-c model_reasoning_effort=high`, `--output-last-message` and reviewer `--output-schema`. `codex exec -` reads its prompt from stdin. `--full-auto` is obsolete in current documentation. The former `codex mcp-server` path was removed in September 2026, so do not build this workflow around stale tutorials.

**Recommended actual chain:** An external Python controller loads tasks and checks prerequisites; optionally asks Claude Opus 5.5 medium for bounded architectural notes using `claude -p`; invokes Codex `gpt-6-luna` with high effort in a new Git worktree; detects file changes and denies out-of-scope/policy/test modifications; executes `docker compose`, pytest, lint and frontend checks independently; invokes `gpt-6.1-sol` read-only with a strict PASS/FAIL JSON schema (medium for security phases, low for simple smoke tasks); repairs only reviewer-identified issues with at most two retries; commits the task and fast-forward merges if all checks pass. No auto-push to main and **never auto-deploy**.

**Important trust limitation**: The included harness is a runnable prototype, not a hardened remote execution service. The same user account generally owns both runner and worktree and may have more privileges than desired. For real unattended use, put AI-written commands inside a fresh disposable VM/container *without network, credentials or host Docker socket*, and run the trusted gate/merger outside that environment. Docker access inside a sandbox can be equivalent to host authority. Git branch protections and independent hosted CI provide a separate trust boundary only if the agent cannot edit CI policies/approve its own PRs.

**Progress storage:** `docs/progress.json` is an inspectable checkpoint, commits are the more reliable state record, and `docs/tasks.json` is the authoritative machine-readable dependency list. A task has one owner and one commit; if a gate fails, mark BLOCKED and save evidence without pretending progress. Require idempotent migrations and ensure checks start against a fresh synthetic DB at CI.

### CI and policies

CI installs the toolchain, checks policy file/test edits against protected `main`, builds Compose images, migrates a new PostgreSQL database, runs Django+FastAPI pytest, Ruff, frontend TS/ESLint/Vitest, OpenAPI generation, and smoke calls. The provided base CI is a *starting point*: it needs `npm`/Python hashes pinned and a proper code-owner review policy before a bank deployment. Add browser E2E and real restore-drill workflow when those features exist. The local test-protection guard is a **policy**, not a magical proof tests cannot be weakened: an attacker can add a permissive codepath or misleading new test. Require independent assertions and security scenarios.

## Worked implementation dependency order

- **P0**: Compose/pgvector/Vite/DRF/FastAPI health, deterministic OpenAPI schema and TS types, baseline CI and locked versions. The skeleton only has basic health/masking demo now.
- **P1**: Admin-controlled identities and two-sided roles; authenticate membership and prove cross-bank boundary at organization level. Do not claim tickets are tenant-tested before tickets exist.
- **P2**: Ticket model/draft/submit (N-10), products, status-action transition matrix, immutable history, lock/version concurrency, rejection/verification-failure/reopen boundaries. Add *two-bank ticket tests* in this phase.
- **P3**: Staff-only task board and comments/attachments, then durable email/in-app notification outbox, reminders and retries.
- **P4**: Reports and exports (default year filter, date/status/bank), overdue warnings, recurring links and bilingual seed data.
- **P5**: Mask before inference; local Sentence-Transformers; Postgres pgvector/keyword dual candidate ranking and RRF; label suggestions and confidence threshold; cluster emerging topics; evaluate Bangla/English with sampled approved synthetic text.
- **P6**: Tamper-evident cryptographic events, chain verification and external anchors, backup/restore drill, strict deployment checklist. Security threats are considered and tested from P0 onward, not postponed until this phase.

Detailed criteria for P0–P2 live in `implementation.md`; machine-executable gates and allowlists in `docs/tasks.json`.

## ML approach and papers

**Similarity:** Input is masked *before* it reaches inference. First narrow by verified `organization_id`, product and recent window, then retrieve candidates from (a) pgvector cosine or inner-product index on normalized embeddings and (b) PostgreSQL `tsvector`/trigram/exact code matches. Combine ranked candidate lists via reciprocal rank fusion, e.g. `score(d) = 1/(k + rank_semantic(d)) + 1/(k + rank_keyword(d))`. The original RRF paper uses rank fusion without training. Cap results to five authorized requests; staff review any high-similarity duplicate. Collect accepted/dismissed outcomes.

**Embedding candidates:** [Multilingual E5 Technical Report](https://arxiv.org/abs/2402.05672), Wang et al. (2024), and [BGE-M3](https://arxiv.org/abs/2402.03216), Chen et al. (2024), are starting points. Do not tune the model based solely on leaderboard numbers; record model revision, checkpoint checksum, vector dimension, memory/CPU latency and held-out Bangla/English Recall@5/Precision@5. E5 family models often require query/document-specific prefixes; follow the selected checkpoint model card. Check license, distribution permissions and embedding-model allowed uses before DataSoft deployment.

**Duplicate evaluation:** Construct synthetic positives using paraphrases, Bangla transliterations, error codes and English/Bangla variants; negatives from superficially similar but different root causes. Test same-tenant recall and cross-tenant absence. Track false positives (staff frustration) separately from false negatives (duplicate work), plus latency and availability. Label suggestions are a ranking/similarity problem against controlled administrator label descriptions; threshold tuned from held-out examples, with 'Other'/none as default when uncertain. Clustering should operate only on masked, low-confidence issues and produce a human-review queue.

**Masking limitations:** Regex/heuristics for card number, account ID, OTP, phone may have false positives and false negatives; use checksum checks where appropriate, avoid retaining OTP/PAN raw, never log original text and limit any unmasked fields to named permissions. For attachments not safely parsable, block inference and require review. Pattern masking is never a guarantee of regulatory compliance.

## Budget and allocation: two $20 subscriptions

- **OpenAI Plus**: As of Nov 2026, published estimates for **local messages per 5-hour window** are GPT-6 Luna **350–3000** and GPT-6.1 Sol **15–160**. These are variable *ranges*, not guaranteed quotas or task counts; weekly caps and shared Work/Codex allowances also apply. Exact usage is displayed in Settings → Usage, not reliably forecastable from task count alone. Not the same as API credits.
- **Claude Pro**: Claude Code is included but Pro limits vary with conversation depth, model, workload and both rolling windows/weekly allowance. There is no substantiated fixed number of end-to-end agent tasks available for $20. If an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is present, vendor CLI may use separately charged API paths: be explicit about subscription authentication and disable unexpected billing.
- **Allocation**: Spend most iterative edits on Luna; reserve Sol medium review for RBAC, multitenancy, workflow and ML/privacy, low for mechanical work. Use Opus 5.5 medium only on initial architecture, complicated blocked phase and final threat-model review, rather than every task. Start with P0–P2 for a coherent prototype, then P3/P4, finally advanced ML and audit. The two subscriptions are plausibly enough for substantial code generation over multiple windows, but **not a commitment to a complete secure production system**; elapsed days and quota resets can't be estimated accurately without observing usage.

## Risks and mitigations

| Failure mode | Required mitigation and validation |
|---|---|
| Agent guesses requirement | Exact N/EX/E IDs in task, traceability matrix, explicit positive/negative tests; stop on conflict. |
| Agent invents CLI option or uses old MCP article | Verify `codex exec --help`, `claude --help`, official docs; version-pin tested CLI in real environment. |
| Tool spends paid API credits unexpectedly | Authenticate subscription-based tools; disallow ambient API keys; inspect usage dashboard, vendor config and billing. |
| Cross-bank data exposure | Server-side permissions, scoped selectors, RLS hardening, two-bank tests for *every* delivery path including exports/search/attachment. |
| Incorrect state transition/concurrent overwrite | One atomic service path, explicit transition table, optimistic version plus row lock, PostgreSQL race tests. |
| False ML duplicate / missing sensitive value | Never merge automatically; threshold+human confirmation; mask-before-inference; offline eval; fail-open portal but fail-closed private processing. |
| False 'CI passed' model statement | Runner independently executes commands and captures process return codes, hosted CI separately. |
| Test tampering or untested bypass | Existing test edits blocked for agent, protected branch and independent policy, manual code-review gate for security releases. |
| Agent prompt-injection through repo/docs/issues | Treat retrieved text as untrusted, no secrets, limited writable roots, review changes to policy files, isolation. |
| Quota exhausted mid-task | Stop with BLOCKED, checkpoint with Git and resume after user has allowance, do not silently switch to paid API. |
| Email sent twice or lost | Outbox transaction, leases, idempotent event keys, retry/poison-message isolation. |
| Hash chain re-computed by privileged attacker | Separate signed external checkpoint / append-only log, independent verification schedule. |
| Database backup unusable | Automate encrypted backups, restore to isolated environment and document a successful restore drill. |
| Supply-chain compromise | Lock exact dependencies, scanner, pinned Actions refs and base-image digests before any privileged deployment. |

## Primary documentation / research links (checked November 14, 2026)

**Current agent tools**

- Anthropic Claude Code memory and imports — https://code.claude.com/docs/en/memory
- Anthropic Claude Code subagents — https://code.claude.com/docs/en/sub-agents
- Anthropic Claude Code hooks — https://code.claude.com/docs/en/hooks
- Anthropic Claude Code settings — https://code.claude.com/docs/en/settings
- Anthropic Claude Code sandbox — https://code.claude.com/docs/en/sandboxing
- Claude Opus 5.5 specifications — https://platform.claude.com/docs/en/models/opus-5-5/overview
- OpenAI Codex noninteractive — https://learn.chatgpt.com/docs/non-interactive-mode
- OpenAI CLI reference — https://learn.chatgpt.com/docs/cli/reference
- OpenAI Codex config reference — https://learn.chatgpt.com/docs/config-file/config-reference
- OpenAI Codex AGENTS — https://learn.chatgpt.com/docs/agent-configuration/agents-md
- OpenAI plan usage — https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex
- OpenAI Codex MCP removal — https://developers.openai.com/blog/openai-for-developers-2025

**Architecture and security**

- Django 6 background Tasks limitations — https://docs.djangoproject.com/en/6.0/topics/tasks/
- DRF schemas/drf-spectacular recommendation — https://www.django-rest-framework.org/api-guide/schemas/
- pgvector Django extension and index — https://github.com/pgvector/pgvector-python
- PostgreSQL locking — https://www.postgresql.org/docs/current/explicit-locking.html
- OWASP Multi Tenant Security — https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
- OWASP Logging — https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OpenAPI TS type generation — https://github.com/openapi-ts/openapi-typescript

**Templates and papers**

- Cookiecutter Django — https://github.com/cookiecutter/cookiecutter-django
- HackSoft Django Styleguide — https://github.com/HackSoftware/Django-Styleguide
- Full Stack FastAPI Template — https://github.com/fastapi/full-stack-fastapi-template
- Bulletproof React — https://github.com/alan2207/bulletproof-react
- RRF — https://doi.org/10.1145/1571941.1572114
- Multilingual E5 — https://arxiv.org/abs/2402.05672
- BGE-M3 — https://arxiv.org/abs/2402.03216

## Clearly identified unknowns

- The supplied requirements set behavior but don't define an approved regulatory/security standard, bank's infrastructure, hosting jurisdiction, data retention policy or precise SLAs. These must be agreed before any production implementation.
- The best model for English/Bangla DataSoft requests and confidence cutoffs cannot be asserted from paper benchmarks alone; collect consented synthetic/approved labeled examples.
- Actual model quotas and CLI versions vary by user/account and date. This report verifies published guidance, not the user's local installation or allowance.
- The generated skeleton has not been run against Docker and authenticated Claude/Codex within this research environment. Static checks do not imply end-to-end runtime correctness.
