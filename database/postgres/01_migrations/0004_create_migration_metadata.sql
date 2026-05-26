-- Phase 1 source: docs/phase_1_database_architecture.md
-- Source design is silent on migration metadata table, so create the required default metadata table.

CREATE TABLE IF NOT EXISTS app_meta.schema_migrations (
    version text PRIMARY KEY,
    description text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    checksum text NULL,
    applied_by text NULL DEFAULT current_user
);

ALTER TABLE app_meta.schema_migrations OWNER TO exam_sys_owner;

COMMENT ON TABLE app_meta.schema_migrations IS 'Tracks applied schema migration versions for exam_sys_dev.';
COMMENT ON COLUMN app_meta.schema_migrations.version IS 'Migration file version key.';
COMMENT ON COLUMN app_meta.schema_migrations.description IS 'Human-readable migration description.';
COMMENT ON COLUMN app_meta.schema_migrations.applied_at IS 'Timestamp when migration version was recorded.';
COMMENT ON COLUMN app_meta.schema_migrations.checksum IS 'Optional migration content checksum.';
COMMENT ON COLUMN app_meta.schema_migrations.applied_by IS 'Database role/user that applied the migration.';

GRANT SELECT, INSERT, UPDATE ON app_meta.schema_migrations TO exam_sys_app;
GRANT SELECT ON app_meta.schema_migrations TO exam_sys_readonly;
