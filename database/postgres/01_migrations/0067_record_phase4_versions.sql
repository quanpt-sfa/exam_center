-- Phase 4.6 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for final Phase 4 hardening idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0066_add_phase4_safe_views_and_grants.sql', 'Add Phase 4 hardening, safe views, and final grants/revokes', NULL, current_user),
    ('0067_record_phase4_versions.sql', 'Record Phase 4.6 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
