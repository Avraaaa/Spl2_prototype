#!/usr/bin/env node
// Hooks must remain fast and offline. Gate suite runs once per task, not per edit.
import { spawnSync } from 'node:child_process';
const result=spawnSync('node',['scripts/validate-repo.mjs'],{stdio:'inherit',timeout:12000});
process.exit(result.status ?? 1);
