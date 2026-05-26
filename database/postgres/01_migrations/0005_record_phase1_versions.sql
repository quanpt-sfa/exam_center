-- Phase 1 source: docs/phase_1_database_architecture.md
-- Record migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0001_create_database_roles.sql', 'Create technical database roles and connect grants', NULL, current_user),
    ('0002_init_extensions.sql', 'Initialize PostgreSQL extensions (none required by Phase 1 source)', NULL, current_user),
    ('0003_create_schemas.sql', 'Create required Phase 1 schemas identity and academic plus app_meta', NULL, current_user),
    ('0004_create_migration_metadata.sql', 'Create app_meta.schema_migrations metadata table', NULL, current_user),
    ('0005_record_phase1_versions.sql', 'Record baseline Phase 1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
