-- Phase 4.3 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for Phase 4.3 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0060_create_submission_seal_and_sealed_answer_tables.sql', 'Create submission.submission_seal and submission.sealed_answer tables', NULL, current_user),
    ('0061_record_phase4_3_versions.sql', 'Record Phase 4.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
