-- Phase 1.1 hardening
-- Record migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0011_add_phase1_fk_indexes.sql', 'Add FK lookup indexes for Phase 1 core tables', NULL, current_user),
    ('0012_add_phase1_partial_unique_indexes.sql', 'Add partial unique indexes for current primary/context rows', NULL, current_user),
    ('0013_harden_phase1_sensitive_access.sql', 'Harden readonly access to sensitive tables and expose safe views', NULL, current_user),
    ('0014_record_phase1_1_versions.sql', 'Record Phase 1.1 hardening migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
