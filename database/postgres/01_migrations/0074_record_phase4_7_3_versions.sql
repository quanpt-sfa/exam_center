-- Phase 4.7.3 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Records migration versions for Phase 4.7.3 assessment modality and question grading profile foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0072_create_exam_version_delivery_profile.sql', 'Create exam_version_delivery_profile table, constraints, indexes, and summary view', NULL, current_user),
    ('0073_create_question_grading_profile.sql', 'Create question_grading_profile table, partial unique indexes, constraints, and summary view', NULL, current_user),
    ('0074_record_phase4_7_3_versions.sql', 'Record Phase 4.7.3 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
