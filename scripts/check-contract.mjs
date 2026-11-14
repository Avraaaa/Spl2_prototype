#!/usr/bin/env node
// Backend-generated OpenAPI is authoritative. This command requires running Docker services.
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
const run = (cmd, args) => {
 const proc=spawnSync(cmd,args,{encoding:'utf8',stdio:'pipe'});
 if (proc.status!==0) throw new Error(`${cmd} ${args.join(' ')} failed: ${proc.stderr}`);
 return proc.stdout;
};
const dir=mkdtempSync(join(tmpdir(),'datasoft-contract-'));
try {
 const original=readFileSync('apps/web/src/api/generated/schema.d.ts','utf8');
 const schema=run('docker',['compose','-f','compose.yaml','exec','-T','api','uv','run','--no-sync','--package','datasoft-api','python','services/api/manage.py','spectacular','--file','/tmp/openapi.yaml','--validate']);
 const actual=run('docker',['compose','-f','compose.yaml','exec','-T','api','cat','/tmp/openapi.yaml']);
 if(actual!==readFileSync('contracts/openapi.yaml','utf8')) throw new Error('Committed OpenAPI is stale');
 run('npm',['run','--prefix','apps/web','generate:api']);
 if(original!==readFileSync('apps/web/src/api/generated/schema.d.ts','utf8')) throw new Error('Generated TypeScript types are stale');
 console.log('PASS: OpenAPI and TypeScript client match.');
} finally { rmSync(dir,{recursive:true,force:true}); }
