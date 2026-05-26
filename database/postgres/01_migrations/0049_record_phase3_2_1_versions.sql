-- Phase 3.2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Records migration versions for Phase 3.2.1 idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0048_create_generated_exam_instance.sql', 'Create delivery.generated_exam_instance immutable snapshot table with constraints/indexes and hardened grants', NULL, current_user),
    ('0049_record_phase3_2_1_versions.sql', 'Record Phase 3.2.1 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
