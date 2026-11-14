-- Apply with a privileged MIGRATION role once; app runtime role needs only DML.
-- This DDL is for reference: production must use Django's VectorExtension migration.
CREATE EXTENSION IF NOT EXISTS vector;
