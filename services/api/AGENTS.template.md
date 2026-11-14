# Django-specific instructions
Python is necessary here and **every execution, migration, test, lint, and dependency change goes through uv**, with `--package datasoft-api` where relevant.
Django alone owns tenants, authorization and SQL writes. Keep `services.py` transactional mutations and `selectors.py` tenant-scoped reads.
Never access a request by unscoped ID first and check permission later. Verify protected responses and attachments for cross-bank isolation.
No changes to issue state outside a transaction; audit event and state update are atomic.
