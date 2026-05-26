INSERT INTO app_meta.schema_migrations (version, description, checksum, applied_by)
VALUES
    (
        '0114_split_api_worker_runtime_db_privileges.sql',
        'Create exam_sys_worker role and split API/worker importing runtime privileges',
        NULL,
        current_user
    ),
    (
        '0115_record_split_api_worker_runtime_db_privileges_versions.sql',
        'Record split API/worker runtime DB privilege migration versions',
        NULL,
        current_user
    )
ON CONFLICT (version) DO NOTHING;

