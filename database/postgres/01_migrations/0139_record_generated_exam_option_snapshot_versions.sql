INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0138_add_generated_exam_option_snapshot_table.sql',
        'Add generated multiple-choice option snapshot table for session-stable runtime identities',
        NULL,
        current_user
    ),
    (
        '0139_record_generated_exam_option_snapshot_versions.sql',
        'Record generated multiple-choice option snapshot migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;