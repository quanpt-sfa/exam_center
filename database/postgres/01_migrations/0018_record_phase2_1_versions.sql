-- Phase 2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Record Phase 2.1 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0015_create_assessment_schema.sql', 'Create assessment schema for Phase 2.1', NULL, current_user),
    ('0016_create_assessment_core_exam_tables.sql', 'Create assessment_type, exam, and exam_version core tables', NULL, current_user),
    ('0017_seed_assessment_types.sql', 'Seed assessment.assessment_type lookup values', NULL, current_user),
    ('0018_record_phase2_1_versions.sql', 'Record Phase 2.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;