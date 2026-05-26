-- Verifies S2W-5.2 capture_job lease/resume schema readiness.

DO
$$
DECLARE
    v_capture_schema_exists boolean;
    v_capture_job_exists boolean;
    v_capture_job_event_exists boolean;

    v_missing_columns text;

    v_idx_status_lease_exists boolean;
    v_idx_lease_owner_exists boolean;

    v_event_check text;
    v_missing_event_tokens text;

    v_app_select_granted boolean;
    v_app_update_granted boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.schemata
        WHERE schema_name = 'capture'
    ) INTO v_capture_schema_exists;

    IF NOT v_capture_schema_exists THEN
        RAISE EXCEPTION 'Expected schema capture to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'capture'
          AND table_name = 'capture_job'
    ) INTO v_capture_job_exists;

    IF NOT v_capture_job_exists THEN
        RAISE EXCEPTION 'Expected table capture.capture_job to exist.';
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
        ON c.table_schema = 'capture'
       AND c.table_name = 'capture_job'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on capture.capture_job: %', v_missing_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'capture'
          AND i.tablename = 'capture_job'
          AND i.indexname = 'idx_capture_capture_job_status_lease_expires_at'
    ) INTO v_idx_status_lease_exists;

    IF NOT v_idx_status_lease_exists THEN
        RAISE EXCEPTION 'Expected idx_capture_capture_job_status_lease_expires_at index to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'capture'
          AND i.tablename = 'capture_job'
          AND i.indexname = 'idx_capture_capture_job_lease_owner_worker_id'
    ) INTO v_idx_lease_owner_exists;

    IF NOT v_idx_lease_owner_exists THEN
        RAISE EXCEPTION 'Expected idx_capture_capture_job_lease_owner_worker_id index to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'capture'
          AND table_name = 'capture_job_event'
    ) INTO v_capture_job_event_exists;

    IF NOT v_capture_job_event_exists THEN
        RAISE EXCEPTION 'Expected table capture.capture_job_event to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_event_check
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'capture'
      AND t.relname = 'capture_job_event'
      AND c.conname = 'ck_capture_capture_job_event_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_event_check IS NULL THEN
        RAISE EXCEPTION 'Expected ck_capture_capture_job_event_type check constraint to exist.';
    END IF;

    WITH required_event_tokens AS (
        SELECT unnest(
            ARRAY[
                'CAPTURE_QUEUED',
                'CAPTURE_STARTED',
                'CAPTURE_RETRIED',
                'CAPTURE_COMPLETED',
                'CAPTURE_FAILED',
                'CAPTURE_CANCELLED',
                'ARTIFACT_CREATED',
                'DATASET_CREATED'
            ]
        ) AS token
    )
    SELECT string_agg(ret.token, ', ' ORDER BY ret.token)
    INTO v_missing_event_tokens
    FROM required_event_tokens ret
    WHERE position(ret.token IN coalesce(v_event_check, '')) = 0;

    IF v_missing_event_tokens IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required capture event tokens in ck_capture_capture_job_event_type: %', v_missing_event_tokens;
    END IF;

    SELECT has_table_privilege('exam_sys_app', 'capture.capture_job', 'SELECT')
    INTO v_app_select_granted;

    IF NOT v_app_select_granted THEN
        RAISE EXCEPTION 'Expected exam_sys_app to retain SELECT privilege on capture.capture_job.';
    END IF;

    SELECT has_table_privilege('exam_sys_app', 'capture.capture_job', 'UPDATE')
    INTO v_app_update_granted;

    IF NOT v_app_update_granted THEN
        RAISE EXCEPTION 'Expected exam_sys_app to retain UPDATE privilege on capture.capture_job.';
    END IF;

    RAISE NOTICE 'PASS: S2W-5.2 capture_job lease/resume schema readiness checks passed.';
END
$$;
