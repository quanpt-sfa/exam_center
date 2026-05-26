-- Phase 1 source: docs/phase_1_database_architecture.md
-- Record version metadata for core table migrations.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0006_create_phase1_core_tables.sql', 'Create Phase 1 core identity and academic tables', NULL, current_user),
    ('0007_add_phase1_core_foreign_keys.sql', 'Add Phase 1 foreign keys without cascade delete on academic history', NULL, current_user),
    ('0008_phase1_core_grants.sql', 'Grant app and readonly permissions on Phase 1 core tables and sequences', NULL, current_user),
    ('0009_seed_identity_roles.sql', 'Seed identity.role baseline role set', NULL, current_user),
    ('0010_record_phase1_core_versions.sql', 'Record Phase 1 core table migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
