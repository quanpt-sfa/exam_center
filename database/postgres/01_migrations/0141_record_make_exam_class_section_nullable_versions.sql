INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0140_make_exam_class_section_nullable.sql',
        'Make class_section_id nullable in assessment.exam table',
        NULL,
        current_user
    ),
    (
        '0141_record_make_exam_class_section_nullable_versions.sql',
        'Record make exam class section nullable migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;
