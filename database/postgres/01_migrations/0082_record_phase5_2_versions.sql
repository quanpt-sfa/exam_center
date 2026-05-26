-- Phase 5.2 source: docs/phase_5a_individual_grading_runtime_design.md
-- Records migration versions for Phase 5.2 question grading task foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0081_create_question_grading_task_table.sql', 'Create Phase 5.2 grading.question_grading_task dispatch table', NULL, current_user),
    ('0082_record_phase5_2_versions.sql', 'Record Phase 5.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
