# Actual current state
- Backend: Django skeleton, health endpoint, PostgreSQL + pgvector migration. **No bank isolation or user management yet.**
- ML: FastAPI health, limited rule masking; Sentence-Transformers dependency deferred into optional `model` extra. No embedding endpoint or validated bilingual similarity yet.
- Frontend: React/TypeScript health-check page. No authenticated portal yet.
- Runner: JS prototype harness, not a security boundary. Requires Codex/Claude CLIs authenticated in local environment and independent CI verification.
- Lockfiles: MUST be generated (`uv lock`, `npm install --prefix apps/web`) on a network-connected development machine, reviewed and committed before first build or agent run.
- Validation: offline structure and JS syntax can be validated here; no Docker or online registry access at artifact-build time.
