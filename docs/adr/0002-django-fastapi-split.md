# ADR-002 — Django authoritative business backend, FastAPI inference boundary
Status: Accepted for prototype
Date: 2026-11-14
Requirement IDs: N-01..N-26, E-01..E-15, EX-01..EX-11

## Context
Four roles, bank isolation, strict transitions and workflow audit are centralized transactional concerns; ML must fail independently.

## Decision
Django owns all persisted data and permissions. FastAPI offers CPU-local masking and embeddings through authenticated private HTTP. No direct ML database connection.

## Consequences
Simple single business write path; early failure isolation; additional private service interface to test. Shared-schema tenancy requires comprehensive negative authorization testing; RLS planned as defense-in-depth.
