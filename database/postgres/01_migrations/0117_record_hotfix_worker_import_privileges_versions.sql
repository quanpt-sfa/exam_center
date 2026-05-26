INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0116_hotfix_worker_import_privileges.sql',
        'Hotfix worker import privileges for exam_sys_worker across importing/identity/academic boundaries',
        NULL,
        current_user
    ),
    (
        '0117_record_hotfix_worker_import_privileges_versions.sql',
        'Record worker import privilege hotfix migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;

