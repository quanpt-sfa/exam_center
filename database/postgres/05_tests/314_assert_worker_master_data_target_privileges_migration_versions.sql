DO
$$
DECLARE
    missing_versions text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0118_hotfix_worker_master_data_target_privileges.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0118_hotfix_worker_master_data_target_privileges.sql';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE version = '0119_record_hotfix_worker_master_data_target_privileges_versions.sql'
    ) THEN
        missing_versions := missing_versions || CASE WHEN missing_versions = '' THEN '' ELSE ', ' END || '0119_record_hotfix_worker_master_data_target_privileges_versions.sql';
    END IF;

    IF missing_versions <> '' THEN
        RAISE EXCEPTION 'Missing worker master-data target privilege hotfix migration versions: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: worker master-data target privilege hotfix migration versions are recorded.';
END
$$;

