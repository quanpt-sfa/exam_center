-- Phase 2.2 source: docs/phase_2_assessment_generator_pipeline.md
-- Record Phase 2.2 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0019_create_question_bank_and_templates.sql', 'Create question bank, templates, template-bank mapping, and parameter definitions', NULL, current_user),
    ('0020_create_reference_solution_and_question_attachment.sql', 'Create reference solution, question attachment, and safe summary view with hardened readonly access', NULL, current_user),
    ('0021_record_phase2_2_versions.sql', 'Record Phase 2.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;