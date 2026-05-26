-- Phase 5.4 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5.4 scoring tables.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0085_create_question_score_and_submission_score_tables.sql', 'Create Phase 5.4 grading.question_score and grading.submission_score tables', NULL, current_user),
    ('0086_record_phase5_4_versions.sql', 'Record Phase 5.4 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
