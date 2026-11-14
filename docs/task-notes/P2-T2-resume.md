Resume P2-T2. The seeded code is the complete P2-T2 workflow implementation plus a draft-edit concurrency change. Everything passes
except existing P2-T1 tests, because `version` was made REQUIRED on draft PATCH. Existing tests are protected and must not be edited
(the harness rejects any change to them). Orchestrator decision:

- Draft PATCH /api/issues/{id}/: `version` is OPTIONAL in the request serializer. If it is provided and differs from the stored
  version -> 409 Conflict and nothing changes (same conflict path as workflow transitions). If it is provided and matches -> save
  and increment version. If it is omitted -> the existing P2-T1 behaviour (validation, 403 for non-draft/non-owner, etc.) must stay
  exactly as before, so all existing tests pass again. Permission/state checks must run before version handling, so a non-editable
  issue still returns 403 (not 400).
- The frontend draft edit form ALWAYS sends the current `version` and shows the existing 409 message.
- Keep/adjust only the NEW P2-T2 tests (test_p2_t2_draft_concurrency.py, test_p2_t2_workflow.py): stale version -> 409 and fields
  unchanged; matching version -> 200 and version incremented; omitted version -> 200 (backward compatible).
- Do not change anything else. TypeScript: with Record<string, unknown> use `x != null && <p/>`. Never run uv/python/pytest/
  manage.py/dev.mjs/check-contract in your sandbox.
