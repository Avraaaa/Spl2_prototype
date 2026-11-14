# ADR-003 — Postgres transactional outbox (not Redis)
Status: Accepted for prototype
Date: 2026-11-14
Requirement IDs: N-17, N-20, N-22, EX-08

## Decision
Django transactional OutboxEvent table with unique event identifiers, atomic status change+enqueue, standalone worker with SKIP LOCKED, bounded retries and periodic scheduling; SMTP configured externally. No Celery/Redis.

## Limits
Not yet implemented. Worker must safely reclaim leases after crashes, prevent concurrent sends, deduplicate by provider message ID, and expose monitoring. Revisit if throughput and latency tests justify a broker.
