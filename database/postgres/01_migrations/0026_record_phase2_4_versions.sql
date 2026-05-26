-- Phase 2.4 source: docs/phase_2_assessment_generator_pipeline.md
-- Record Phase 2.4 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0024_create_grader_module_and_profile_tables.sql', 'Create grader_module, grader_module_version, grading_profile, and safe summary view', NULL, current_user),
    ('0025_seed_grader_modules.sql', 'Seed grader modules and initial v1 module versions', NULL, current_user),
    ('0026_record_phase2_4_versions.sql', 'Record Phase 2.4 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;