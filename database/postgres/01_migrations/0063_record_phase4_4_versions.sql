-- Phase 4.4 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for Phase 4.4 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0062_create_answer_conflict_table.sql', 'Create submission.answer_conflict conflict and recovery metadata table', NULL, current_user),
    ('0063_record_phase4_4_versions.sql', 'Record Phase 4.4 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
