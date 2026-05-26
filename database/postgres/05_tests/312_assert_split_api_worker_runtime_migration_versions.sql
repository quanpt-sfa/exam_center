DO
$$
DECLARE
    missing_versions text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0114_split_api_worker_runtime_db_privileges.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0114_split_api_worker_runtime_db_privileges.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0115_record_split_api_worker_runtime_db_privileges_versions.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0115_record_split_api_worker_runtime_db_privileges_versions.sql';
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing split API/worker runtime migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: split API/worker runtime migration versions are recorded.';
END
$$;

