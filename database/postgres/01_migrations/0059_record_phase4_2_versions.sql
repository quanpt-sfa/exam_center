-- Phase 4.2 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Records migration versions for Phase 4.2 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0058_create_answer_state_and_autosave_tables.sql', 'Create submission.answer_state, submission.answer_save_batch, and submission.answer_save_item tables', NULL, current_user),
    ('0059_record_phase4_2_versions.sql', 'Record Phase 4.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
