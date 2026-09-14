-- C-EA1-D3 least-privilege PostgreSQL roles. Run as the generated RDS admin.
-- Passwords are not accepted here; runtime principals use RDS IAM authentication.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_archive_catalogue') THEN
    CREATE ROLE carbon_archive_catalogue NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_archive_journal') THEN
    CREATE ROLE carbon_archive_journal NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_archive_audit') THEN
    CREATE ROLE carbon_archive_audit LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_archive_supervisor') THEN
    CREATE ROLE carbon_archive_supervisor LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_archive_recovery') THEN
    CREATE ROLE carbon_archive_recovery LOGIN;
  END IF;
END
$$;

ALTER ROLE carbon_archive_catalogue NOLOGIN;
ALTER ROLE carbon_archive_journal NOLOGIN;
ALTER ROLE carbon_archive_audit LOGIN;
ALTER ROLE carbon_archive_supervisor LOGIN;
ALTER ROLE carbon_archive_recovery LOGIN;

GRANT rds_iam TO carbon_archive_supervisor, carbon_archive_audit, carbon_archive_recovery;
GRANT CONNECT ON DATABASE carbon_archive TO carbon_archive_supervisor, carbon_archive_audit, carbon_archive_recovery;
GRANT USAGE ON SCHEMA public TO carbon_archive_catalogue, carbon_archive_journal, carbon_archive_audit;

GRANT SELECT, INSERT, UPDATE ON
  cea1_admission, cea1_entry, cea1_artifact, cea1_event, cea1_outbox,
  cea1_consumer_effect, cea1_acknowledgement, cea1_artifact_availability,
  cea1_orphan, cea1_schema_meta
TO carbon_archive_catalogue;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO carbon_archive_catalogue;

GRANT SELECT, INSERT, UPDATE ON
  cea1_alpha_capacity_meta, cea1_alpha_capacity_reservation,
  cea1_alpha_capacity_event
TO carbon_archive_journal;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO carbon_archive_journal;

GRANT SELECT ON ALL TABLES IN SCHEMA public TO carbon_archive_audit;
GRANT carbon_archive_catalogue, carbon_archive_journal TO carbon_archive_supervisor;
GRANT carbon_archive_audit TO carbon_archive_recovery;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO carbon_archive_audit;
