-- Phase 3.2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Records migration versions for Phase 3.2.2 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0050_create_generated_exam_question_tables.sql', 'Create generated_exam_question and generated_question_parameter snapshot tables', NULL, current_user),
    ('0051_create_generated_expected_answer_table.sql', 'Create generated_expected_answer snapshot table with hardening', NULL, current_user),
    ('0052_record_phase3_2_2_versions.sql', 'Record Phase 3.2.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
