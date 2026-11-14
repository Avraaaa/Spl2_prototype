# learning.md — findings for agents implementing the DataSoft portal

Read this before starting any task. Each entry is something that already cost time or caused a bug.
Maintained by the orchestrator (Claude); coder agents must not edit it (protected in agent-runner).
Requirements source: `docs/requirements/qfd.md`. Plan: `implementation.md`. Tasks: `docs/tasks.json`.

## 1. Process rules (owner decisions)
- **Codex implements, Claude orchestrates and reviews.** Claude only fixes orchestration/tooling. If Codex is unavailable, stop and ask; do not silently code instead.
- **The owner is the sole commit author.** Never add `Co-Authored-By:` or "Generated with" lines. The runner commits with the local git identity.
- Never `git push`, deploy, or use real bank data. Use synthetic names only. Avoid real Bangladeshi bank names (e.g. "Meghna" is a real bank); the seed uses "Northwind Demo Bank" (NWD) and "Riverstone Demo Bank" (RSD).
- Email features are **deferred to P3-T3** (held until the owner sets up email). Do not add SMTP settings, an organization contact email, or emailed credentials earlier. Interim: the admin sees the temporary password once.
- When `implementation.md` and the QFD disagree, the QFD wins unless an owner decision in `implementation.md` says otherwise.

## 2. Native Windows environment (no WSL2, no Docker locally)
- Host: Windows 11, PowerShell; the Bash tool is Git Bash. PostgreSQL 18 is at `C:\Program Files\PostgreSQL\18` (psql is not on PATH), with pgvector 0.8 installed.
- **pgvector is not a trusted extension.** A non-superuser cannot `CREATE EXTENSION vector`. `scripts/dev-db-setup.sql` creates it as superuser in `datasoft` **and `template1`**, so the pytest test DB inherits it and the `VectorExtension` migration is a no-op. The `datasoft` role has CREATEDB (needed for `test_datasoft`).
- **`.env` / `.env.*` reads are denied** by `.claude/settings.json`. Synthetic local defaults live in `scripts/dev.mjs`; real env vars override them. Run everything through it:
  - `node scripts/dev.mjs` (migrate + Django :8000 + Vite :5173), `migrate`, `seed`, `test`, `lint`, `pytest <args>`, `manage <args>`.
  - Running `uv run ... pytest` directly fails with `fe_sendauth: no password supplied`, or with `RuntimeError: A production DJANGO_SECRET_KEY is required` when `DJANGO_DEBUG` is unset (settings fail closed at import).
- Node 26 refuses to spawn `.cmd` shims (npm, codex) without `shell: true`. All Node scripts that spawn npm/codex use `shell: true` with fixed, quoted arguments.
- Git Bash `tar -xf E:/...` treats `E:` as a remote host. Use `unzip` or copy the file first.
- `core.autocrlf` is on. `.gitattributes` forces LF, otherwise ruff/prettier and the contract freshness check fight over line endings. Contract comparisons normalise `\r\n`.
- Avoid clever shell tricks (e.g. `python - <<EOF || other`): the system Python 3.10 ran an empty script and "succeeded". Edit files with real edits and verify.

## 3. Python / Django tooling
- ruff needs `src = ["services/api", "services/ml"]`, or it misclassifies first-party imports (`app`, `domains`) as third-party.
- mypy needs `mypy_path = "services/api"` for the django-stubs plugin (`No module named 'config'`) and `DJANGO_DEBUG=1` (the dev.mjs `lint` command provides it).
- `services/ml/pytest.ini` needs `pythonpath = .`, because pytest's rootdir becomes `services/ml` and the root pyproject's pythonpath is ignored.
- Domain apps live in `services/api/domains/<name>` with `name = "domains.<name>"` and a short `label`; `domains/__init__.py` must exist.
- **Test speed:** Django's default PBKDF2 hashing made 24 tests take 71 s. `tests/conftest.py` sets the MD5 hasher for tests only (2.5 s). Keep production hashers untouched.
- **Throttle state leaks between tests** (LocMem cache, keyed by 127.0.0.1). `conftest.py` clears the cache autouse; keep it if you add throttles.
- Fixtures: `conftest.py` provides `datasoft`, `bank_a`, `bank_b`, `admin`, `support`, `officer_a`, `officer_b`, `make_user`, `client_for(user)` (force-auth) and `login(username, password)` (real session login). Use two banks in every isolation test.

## 4. DRF / security pitfalls (real bugs found)
- **Explicit `permission_classes` replace the DRF defaults.** The global first-login gate (`PasswordChangeCompleted`) silently disappeared on admin views. Always build view permissions from a shared list (see `ADMIN_PERMISSIONS` in `domains/accounts/api.py`) that repeats `IsAuthenticated, HasPortalAccount, PasswordChangeCompleted`.
- DRF `APIView` is `csrf_exempt`, and `SessionAuthentication` enforces CSRF only for authenticated users. **Login must be wrapped with `csrf_protect`**. Test CSRF with `APIClient(enforce_csrf_checks=True)`; the default test client skips CSRF entirely.
- To return a machine-readable code from a permission, raise `PermissionDenied({"detail": ..., "code": ...})` (a dict detail becomes the body).
- Temporary-credential expiry must be enforced **everywhere it matters**: at login *and* at change-password (review finding).
- Changing a password rotates the session auth hash. Call `update_session_auth_hash` after a self-service change, or the user is logged out. Admin resets intentionally kill sessions.
- Deactivation: `user.is_active=False` makes `ModelBackend.get_user` return None, so live sessions die immediately. Never delete users; FKs use PROTECT to preserve history.
- Logout is `AllowAny` and idempotent (204), so a 403 always means a CSRF failure with the session still alive. **The frontend must only clear local auth state after a 2xx logout** (review finding).
- Organization/bank is always derived from `request.user.account`; never accept it from headers, query or body (tests cover spoofing).
- Services raise Django `ValidationError`/`PermissionDenied`; API views translate them to DRF exceptions (`_translate`). Keep business rules in `services.py`, not views.
- Append-only models override `save`/`delete` to refuse updates (see `AccountEvent`).

## 5. OpenAPI contract and frontend
- The contract is generated: `node scripts/check-contract.mjs --write` regenerates `contracts/openapi.yaml` and `apps/web/src/api/generated/schema.d.ts`. `test_openapi_contract.py` fails if it is stale. Never hand-edit either file.
- Use `extend_schema` on every view with explicit request/response serializers, and `@extend_schema_field` on `SerializerMethodField`, otherwise types degrade to `string`/`any` (roles became `string[]` until fixed). Spectacular runs with `--fail-on-warn`.
- `COMPONENT_SPLIT_REQUEST=True` creates `XRequest` vs `X` component types; use the right one in the frontend.
- openapi-fetch paths include `/api/...`, so `baseUrl` is the page origin; the Vite proxy forwards `/api` to Django. The client adds `X-CSRFToken` from the `csrftoken` cookie on unsafe methods; call `GET /api/auth/csrf/` before login.
- ESLint flags unused mock parameters. Type mocks as `vi.fn<(input: Request) => Promise<Response>>(async () => ...)`; don't use `void x ||` hacks (TS2873).
- No React Testing Library/jsdom is installed. Put UI logic in pure functions (e.g. `features/auth/roles.ts`) and unit-test those; verify screens in a real browser.
- The UI only hints at permissions; Django decides. Every button must call a real endpoint.

## 6. QFD details that are easy to miss
- N-04: the **Administrator can do everything a Support Agent can**. Every DataSoft-side workflow permission must accept both roles.
- N-16/N-17: delivering moves the request to **Awaiting Client Verification** and notifies the Verifier. Actual delivery date is set at delivery; tentative date is shown next to it.
- N-12: rejection reason is **client-visible**; accept needs a tentative date or "to be provided later"; every tentative-date change is kept in history and shown to the client.
- N-19: reopen within a configurable 30 days (Admin setting) by Issue Officer, Issue Verifier **or** DataSoft, reason required; after that, a new **Recurring** request linked to the old one (N-11, same bank only).
- N-20: no automatic verification or closure; reminders only.
- N-06: request types are bug/change/feature/support, with urgency/priority. N-07: readable IDs like `SR-1024`.
- N-24: the Detailed report has a fixed column list (ID, bank, officer, title, detail, status, created, submitted, tentative and actual delivery, last status update, closure date).

## 7. Orchestration (agent-runner on Windows)
- `codex` is an npm `.cmd` shim, so it must be spawned with `shell: true`. The `codex exec --sandbox read-only` review works with ChatGPT login. Leave out `--model` unless `DATASOFT_CODER_MODEL`/`DATASOFT_REVIEWER_MODEL` are set.
- Gates come from `docs/tasks.json` and run natively through `scripts/dev.mjs` (Docker gates are kept only for later integration work).
- A fresh worktree has no `.venv` or `node_modules`. The runner runs `uv sync --locked` and `npm ci --prefix apps/web` there before the coder starts.
- **`CLAUDE.md` is intentionally untracked** (in `.gitignore`, owner decision; never commit it). A fresh worktree therefore lacks it and `validate-repo.mjs` fails with `Missing CLAUDE.md`. The runner copies the local `CLAUDE.md` into the worktree. Versioned agent policy (e.g. sole authorship) lives in `AGENTS.template.md`.
- Check that every gate passes on an untouched worktree of HEAD before blaming the coder for a gate failure.
- **The Codex `workspace-write` sandbox on Windows cannot run Python.** `uv run` fails with `Failed to initialize cache ... os error 183`, and even `.venv\Scripts\python.exe` fails with `did not find executable at ...\AppData\Roaming\uv\python\...\python.exe: Access is denied`. Widening the sandbox (extra writable roots) is not acceptable. So:
  - coder agents write Python code, hand-written migrations and pytest tests without running them;
  - the harness runs `node scripts/check-contract.mjs --write` after each coder attempt (the generated files are always allowed), then the gates, and sends the failure log back (retry budget 3);
  - Node works in the sandbox (`npm run --prefix apps/web check`), but new endpoint types exist only after the harness regenerates the schema.
- An interrupted run can be resumed: save the worktree diff (`git add -N <new files>; git diff --binary > .agent_runs/seeds/<task>.patch`) and run `node scripts/agent-runner.mjs --task <id> --seed-patch <file>`.
- Stopping the runner mid-task (TaskStop) skips its cleanup. Remove the leftover worktree with `git worktree remove --force <path>` and delete the `agent/<task>-<sha>` branch.
