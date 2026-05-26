-- Verifies S2W-4.1C grading claim/run schema readiness without modifying schema.

DO
$$
DECLARE
    v_job_table_exists boolean;
    v_run_table_exists boolean;
    v_event_table_exists boolean;
    v_job_status_check text;
    v_run_status_check text;
    v_event_type_check text;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_job'
    ) INTO v_job_table_exists;

    IF NOT v_job_table_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_job to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_run'
    ) INTO v_run_table_exists;

    IF NOT v_run_table_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_run to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_event'
    ) INTO v_event_table_exists;

    IF NOT v_event_table_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_event to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_job_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_job'
      AND c.conname = 'ck_grading_grading_job_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_job_status_check IS NULL
       OR position('QUEUED' in v_job_status_check) = 0
       OR position('RUNNING' in v_job_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected grading_job status check to allow QUEUED and RUNNING. Found: %', coalesce(v_job_status_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_run_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_run'
      AND c.conname = 'ck_grading_grading_run_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_run_status_check IS NULL
       OR position('RUNNING' in v_run_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected grading_run status check to allow RUNNING. Found: %', coalesce(v_run_status_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_event_type_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_event'
      AND c.conname = 'ck_gr_ge_event_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_event_type_check IS NULL
       OR position('JOB_STARTED' in v_event_type_check) = 0
       OR position('RUN_STARTED' in v_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected grading_event event_type check to allow JOB_STARTED and RUN_STARTED. Found: %', coalesce(v_event_type_check, '<missing>');
    END IF;

    RAISE NOTICE 'PASS: S2W-4.1C grading claim/run schema readiness checks passed.';
END
$$;
