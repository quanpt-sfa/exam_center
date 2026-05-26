INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0142_create_exam_sitting_class_section.sql',
        'Create delivery.exam_sitting_class_section join table',
        NULL,
        current_user
    ),
    (
        '0143_record_create_exam_sitting_class_section_versions.sql',
        'Record create exam sitting class section migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;
