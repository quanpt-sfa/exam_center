INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0122_clear_placeholder_system_logo.sql',
        'Clear placeholder system logo URL (https://example.com/logo.png) by setting it to NULL',
        NULL,
        current_user
    ),
    (
        '0123_record_clear_placeholder_system_logo_versions.sql',
        'Record clear placeholder system logo schema migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;
