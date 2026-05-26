-- Phase 2.3 source: docs/phase_2_assessment_generator_pipeline.md
-- Record Phase 2.3 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0022_create_exam_blueprint_tables.sql', 'Create exam blueprint, section, rule, and rule-question tables', NULL, current_user),
    ('0023_record_phase2_3_versions.sql', 'Record Phase 2.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;