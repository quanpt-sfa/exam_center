INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0118_hotfix_worker_master_data_target_privileges.sql',
        'Complement 0114 by granting exam_sys_worker access to identity/academic master-data target tables',
        NULL,
        current_user
    ),
    (
        '0119_record_hotfix_worker_master_data_target_privileges_versions.sql',
        'Record worker master-data target privilege hotfix migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;

