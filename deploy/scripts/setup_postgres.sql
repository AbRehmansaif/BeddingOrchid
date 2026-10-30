-- ==============================================================================
-- PostgreSQL Setup for BeddingOrchid (6th Site on Shared VPS)
-- Execute as postgres user:
--   sudo -u postgres psql -f deploy/scripts/setup_postgres.sql
-- Or run line by line in psql.
-- ==============================================================================

-- 1. Create Dedicated Role/User
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE rolname = 'beddingorchid_user') THEN
      CREATE ROLE beddingorchid_user WITH LOGIN PASSWORD 'YourStrongSecretPassword123!';
   ELSE
      ALTER ROLE beddingorchid_user WITH PASSWORD 'YourStrongSecretPassword123!';
   END IF;
END
$do$;

-- 2. Create Dedicated Database
SELECT 'CREATE DATABASE beddingorchid_db OWNER beddingorchid_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'beddingorchid_db')\gexec

-- 3. Grant Privileges
GRANT ALL PRIVILEGES ON DATABASE beddingorchid_db TO beddingorchid_user;

-- For PostgreSQL 15+ (Grant schema permissions on public schema):
\connect beddingorchid_db
GRANT ALL ON SCHEMA public TO beddingorchid_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO beddingorchid_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO beddingorchid_user;

