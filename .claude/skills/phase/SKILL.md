---
name: phase
description: Review the next implementation phase and launch only a bounded task.
---
Read `docs/tasks.json` and `docs/progress.json`. Summarize one next task's prerequisites, file boundaries and gates.
If user wants automation, recommend `node scripts/agent-runner.mjs --task ID` after initial `npm run setup` and clean Git commit.
Never start multiple coder sessions on the same worktree. Do not bypass the runner.
