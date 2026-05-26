-- Phase 4.5 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for Phase 4.5 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0064_create_capture_schema_and_capture_job_tables.sql', 'Create capture schema and post-seal capture foundation tables', NULL, current_user),
    ('0065_record_phase4_5_versions.sql', 'Record Phase 4.5 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
