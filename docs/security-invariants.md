# Mandatory safety invariants

1. Derive bank membership on server from authenticated user. Every ticket-derived query, download, export, report, comment, file and notification must require a matching bank; DataSoft-wide queries require an explicit staff-only policy. Include negative cross-bank tests for LIST, GET, SEARCH, EXPORT, ATTACHMENT, ML SUGGESTIONS.
2. Client-visible and internal content are different data classes and serializer/query policies. Internal notes/tasks/commit links are never in a client API response.
3. Every transition is a named service with explicit allowed current states and actor roles, atomic append-only event, version check, and row lock. Reasons mandatory for rejection, verification failure, and reopening.
4. All delivery-date edits and status decisions have actor and timestamp. Client verification and DataSoft closure are distinct.
5. Only the Issue Officer authorizes submission; issue Verifier confirms delivery; only DataSoft closes. Verify dual-role membership works.
6. No raw OTP or full PAN retained; masking is performed synchronously in Django BEFORE writing content, queuing jobs, or NLP calls. Regex is heuristic; human mask review and data handling policy still required.
7. Never expose customer data to external AI, telemetry or logs. Use synthetic bank examples only.
8. Files are private, scanned, size/type limited, served through tenant-checked Django endpoint or appropriately constrained signed links; signed object keys are not public URLs.
9. Audit records are append-only to application roles, hash chain per defined scope, periodically anchored to a separate security principal/storage; verify hash-chain and missing event continuity.
10. Email outbox is transactionally committed, idempotent, retried with capped backoff and terminal failure; no plaintext secrets in logs.
11. Authentication: hashed temporary credentials, short expiry, first-login password reset, replay prevention, rate limits, CSRF, secure cookies and one-time recovery. The requirement to email raw temporary passwords is a security exception needing client signoff; prefer one-time setup link in production.
12. CI checks immutable security tests from protected main branch. Block merge if protected tests/config/required checks modified without a separately approved security change.
