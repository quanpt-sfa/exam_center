-- Verifies S2W-4H-C lease/resume schema readiness for grading job runtime.

DO
$$
DECLARE
    v_grading_job_exists boolean;
    v_missing_columns text;

    v_idx_lease_expires_exists boolean;
    v_idx_lease_owner_exists boolean;
    v_idx_running_lease_exists boolean;

    v_lease_check text;

    v_app_update_granted boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_job'
    ) INTO v_grading_job_exists;

    IF NOT v_grading_job_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_job to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'lease_owner_worker_id',
                'lease_expires_at',
                'last_heartbeat_at'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'grading_job'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.grading_job: %', v_missing_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'grading_job'
          AND i.indexname = 'idx_grading_grading_job_lease_expires_at'
    ) INTO v_idx_lease_expires_exists;

    IF NOT v_idx_lease_expires_exists THEN
        RAISE EXCEPTION 'Expected idx_grading_grading_job_lease_expires_at index to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'grading_job'
          AND i.indexname = 'idx_grading_grading_job_lease_owner_worker_id'
    ) INTO v_idx_lease_owner_exists;

    IF NOT v_idx_lease_owner_exists THEN
        RAISE EXCEPTION 'Expected idx_grading_grading_job_lease_owner_worker_id index to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'grading_job'
          AND i.indexname = 'idx_grading_grading_job_running_lease_expires'
    ) INTO v_idx_running_lease_exists;

    IF NOT v_idx_running_lease_exists THEN
        RAISE EXCEPTION 'Expected idx_grading_grading_job_running_lease_expires partial index to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_lease_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_job'
      AND c.conname = 'ck_grading_grading_job_lease_owner_expires_consistency'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_lease_check IS NULL THEN
        RAISE EXCEPTION 'Expected ck_grading_grading_job_lease_owner_expires_consistency check constraint to exist.';
    END IF;

    SELECT has_table_privilege('exam_sys_app', 'grading.grading_job', 'UPDATE')
    INTO v_app_update_granted;

    IF NOT v_app_update_granted THEN
        RAISE EXCEPTION 'Expected exam_sys_app to retain UPDATE privilege on grading.grading_job.';
    END IF;

    RAISE NOTICE 'PASS: S2W-4H-C lease/resume schema readiness checks passed.';
END
$$;
