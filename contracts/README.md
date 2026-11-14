# Public API contract — Django is authoritative

`contracts/openapi.yaml` is **not hand-authored**. Phase P0-T2 must generate it using `drf-spectacular` and commit both the updated schema and frontend generated types.

```bash
docker compose -f compose.yaml exec -T api uv run --no-sync --package datasoft-api python services/api/manage.py spectacular --file /tmp/openapi.yaml --validate
docker compose -f compose.yaml exec -T api cat /tmp/openapi.yaml > contracts/openapi.yaml
npm run --prefix apps/web generate:api
node scripts/check-contract.mjs
```

These commands require `uv.lock`, `apps/web/package-lock.json` and running Docker containers. Never hand-copy Django serializers into TypeScript types; use `openapi-typescript`/`openapi-fetch`.
