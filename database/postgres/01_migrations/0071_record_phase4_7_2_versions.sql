-- Phase 4.7.2 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Records migration versions for Phase 4.7.2 capture profile and extractor foundation.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0070_create_capture_profiles_and_extractors.sql', 'Create capture profile, extractor query, and capture-profile-to-engine link foundation', NULL, current_user),
    ('0071_record_phase4_7_2_versions.sql', 'Record Phase 4.7.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;
