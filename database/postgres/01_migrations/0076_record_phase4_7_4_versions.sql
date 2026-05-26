-- Phase 4.7.4 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Records migration versions for Phase 4.7.4 exam session resource binding foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0075_create_exam_session_resource_binding.sql', 'Create delivery.exam_session_resource_binding with constraints, indexes, and summary view', NULL, current_user),
    ('0076_record_phase4_7_4_versions.sql', 'Record Phase 4.7.4 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
