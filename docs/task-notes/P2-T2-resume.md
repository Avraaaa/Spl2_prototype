Resume P2-T2. The seeded code is the complete P2-T2 workflow implementation: it passes ALL five gates (169 backend tests,
clean TypeScript), and the independent review found exactly ONE blocking defect. Fix only that, plus its test:

[blocking] Draft edits ignore optimistic concurrency (EX-11). PATCH /api/issues/{id}/ (services/api/domains/issues/api.py,
around line 113) accepts no `version`, and edit_draft() in services/api/domains/issues/services.py (around line 112) overwrites
fields after select_for_update without comparing versions. Required:
- The draft PATCH request must include `version` (required field in the write serializer for updates).
- In edit_draft, after select_for_update, if issue.version != the client's version, raise the same conflict error the workflow
  transitions use, so the API returns 409 Conflict; otherwise apply the changes and increment version.
- The frontend draft edit form must send the current `version` and show the existing 409 message
  ("This request was changed by someone else — reload").
- Tests: a stale draft PATCH returns 409 and does not change the stored fields; a fresh PATCH succeeds and increments version.

Do not change anything else. TypeScript tip: with `details: Record<string, unknown>`, write `details.x != null && <p>...</p>`
(not `details.x && ...`, which has type unknown). Never run uv/python/pytest/manage.py/dev.mjs/check-contract in your sandbox.
