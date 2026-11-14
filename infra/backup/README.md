# Backup and restore drill (scheduled P6)
Use `pg_dump` on a separate backup identity to secure storage, encrypt backups,
verify checksums, and rehearse `pg_restore` into a disposable PostgreSQL+pgvector
instance. Record test artifacts (no customer data), RPO, RTO and restore outcomes.
Do not attach the production Docker volume to tests. Backing up the database alone
does not cover uploaded files, external audit anchors or the notification delivery history.
