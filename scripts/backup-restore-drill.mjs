#!/usr/bin/env node

/**
 * Disposable PostgreSQL backup/restore rehearsal.
 *
 * Required environment variables:
 *   BACKUP_DRILL_DATABASE       source database name
 *   BACKUP_DRILL_RESTORE_DB     disposable restore database name
 * Optional: PGHOST, PGPORT, PGUSER, PGPASSWORD, BACKUP_DRILL_FILE
 */
import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const source = process.env.BACKUP_DRILL_DATABASE;
const restore = process.env.BACKUP_DRILL_RESTORE_DB;
const backupFile = process.env.BACKUP_DRILL_FILE ?? `${process.cwd()}\\backup-drill.dump`;

if (!source || !restore || source === restore) {
  console.error('Set distinct BACKUP_DRILL_DATABASE and BACKUP_DRILL_RESTORE_DB names first.');
  process.exit(2);
}

const run = (command, args) => {
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
};

run('pg_dump', ['--format=custom', '--file', backupFile, source]);
if (!existsSync(backupFile)) {
  console.error(`Backup file was not created: ${backupFile}`);
  process.exit(1);
}
run('createdb', [restore]);
run('pg_restore', ['--exit-on-error', '--dbname', restore, backupFile]);
console.log(`Backup and restore drill completed for disposable database ${restore}.`);
