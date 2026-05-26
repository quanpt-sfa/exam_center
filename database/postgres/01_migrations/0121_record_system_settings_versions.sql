INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0120_create_system_settings.sql',
        'Create system settings table and settings change history audit trail log in ops schema',
        NULL,
        current_user
    ),
    (
        '0121_record_system_settings_versions.sql',
        'Record system settings schema tables migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;
