-- Phase 4.1 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for Phase 4.1 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0056_create_submission_schema_and_exam_submission.sql', 'Create submission schema and submission.exam_submission runtime container table', NULL, current_user),
    ('0057_record_phase4_1_versions.sql', 'Record Phase 4.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
