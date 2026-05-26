-- Phase 3.0.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Record Phase 3.0.2 migration versions idempotently.

INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    ('0031_create_identity_person_photo.sql', 'Create identity.person_photo with historical tracking and restricted readonly access', NULL, current_user),
    ('0032_create_delivery_schema_and_sitting_tables.sql', 'Create delivery schema and foundational exam sitting and sitting room tables', NULL, current_user),
    ('0033_create_proctor_assignment_table.sql', 'Create delivery.proctor_assignment table and indexes', NULL, current_user),
    ('0034_record_phase3_0_2_versions.sql', 'Record Phase 3.0.2 migration versions', NULL, current_user)
ON CONFLICT (version) DO NOTHING;