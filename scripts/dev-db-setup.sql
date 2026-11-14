-- One-time LOCAL development database setup for native Windows PostgreSQL.
-- Run as the PostgreSQL superuser, e.g.:
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f scripts/dev-db-setup.sql
-- Synthetic local credentials only. Never reuse for any shared or production database.
-- pgvector is not a "trusted" extension, so it is created by the superuser here; the
-- application's VectorExtension migration then becomes a no-op (CREATE EXTENSION IF NOT EXISTS).
-- Creating it in template1 makes it available in the pytest test database as well.

CREATE ROLE datasoft LOGIN CREATEDB PASSWORD 'datasoft-local-dev';
CREATE DATABASE datasoft OWNER datasoft;
\c template1
CREATE EXTENSION IF NOT EXISTS vector;
\c datasoft
CREATE EXTENSION IF NOT EXISTS vector;
