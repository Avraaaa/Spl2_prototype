# What has been validated

- `node scripts/validate-repo.mjs`: PASS (55 requirement IDs, 12 ordered tasks, uv policy and ignored files).
- `node --check scripts/*.mjs`: PASS.
- `uv run --no-project --offline python -m compileall -q services`: PASS (syntax only).
- Python TOML, JSON and YAML syntax: PASS.
- A throwaway Git checkout/worktree test confirmed ignored AGENTS files are regenerated from tracked templates.
- `uv lock`: NOT RUN successfully. This environment cannot connect to PyPI; generate a real lockfile on your machine.
- `npm install`: NOT RUN successfully. This environment cannot connect to npm; generate package-lock.json on your machine.
- Docker Compose build/integration, app lint, unit tests, CI, Codex/Claude CLI end-to-end: NOT EXECUTED here. Required after generating lockfiles and pulling images.

**Do not connect the scaffold to real bank data or production services.**
