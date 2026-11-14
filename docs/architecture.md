# Architecture decision summary (2026-11-14)

**Authority:** Django + DRF. Django authenticates, derives principal roles/tenants, authorizes every operation, owns transactions, writes audit records, emits notification outbox events, exports reports and owns SQL/vector persistence.

**ML:** FastAPI is a stateless inference boundary. Django sends masked text and product/module hints over private network with service authentication; never `tenant_id` or raw attachments. Django itself filters the candidate pool before applying optional model scores. A failed request yields 200 with no suggestions or clear retryable UX; primary user action continues.

**Web:** Vite + React + TypeScript strict. React Router for routes, TanStack Query for asynchronous server state, openapi-typescript and openapi-fetch for generated contracts. Plain CSS for prototype and accessibility; avoid a component framework until design requirements warrant one.

**Data:** PostgreSQL 18/pgvector shared-schema tables with obligatory tenant_id. Application-layer queryset scoping everywhere plus PostgreSQL RLS in a later security hardening phase. RLS must be configured with a separate non-bypass runtime role and transaction-local tenant context. No untested broad RLS policies on DataSoft global reports.

**Outbox:** All outgoing email/notification jobs persist in the same transaction as a workflow event. Separate Django worker leases jobs with `FOR UPDATE SKIP LOCKED`, retries with bounded backoff and idempotency; PostgreSQL only, no Redis. Do not add a task package until requirements demand it.

**Session:** Same-origin session-cookie authentication + CSRF, not tokens stored in browser storage. In development Vite reverse proxies `/api/` to Django.

**Deployment:** Local Compose runs all containers. Production topology is deliberately a sample; provision reverse proxy HTTPS, secret store, mail relay, backup/restore, object storage and independent audit anchors before client acceptance. Pin base image digests and dependency lockfiles before release.

**Alternatives rejected:** FastAPI for all business APIs duplicates Django admin/auth/workflows; Django Ninja is viable but DRF+drf-spectacular has established auth/serializer/API schema conventions; Celery/Redis is extra operational load for a small volume; Next.js SSR adds an unnecessary web server; broad cross-repo instruction dumps worsen context use.
