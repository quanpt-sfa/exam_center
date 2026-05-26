-- Verifies S2W-3.2 dispatcher outcome table, key constraints, and latest view exist.

DO
$$
DECLARE
    v_table_exists boolean;
    v_view_exists boolean;
    v_constraints integer;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'submission'
          AND table_name = 'submission_dispatch_outcome'
    ) INTO v_table_exists;

    IF NOT v_table_exists THEN
        RAISE EXCEPTION 'Expected table submission.submission_dispatch_outcome to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.views
        WHERE table_schema = 'submission'
          AND table_name = 'v_submission_dispatch_latest'
    ) INTO v_view_exists;

    IF NOT v_view_exists THEN
        RAISE EXCEPTION 'Expected view submission.v_submission_dispatch_latest to exist.';
    END IF;

    SELECT COUNT(*)
    INTO v_constraints
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'submission'
      AND t.relname = 'submission_dispatch_outcome'
      AND c.conname IN (
          'ck_sub_dispatch_outcome_route',
          'ck_sub_dispatch_outcome_status',
          'fk_sub_dispatch_outcome_submission',
          'fk_sub_dispatch_outcome_capture_job',
          'fk_sub_dispatch_outcome_grading_job'
      );

    IF v_constraints <> 5 THEN
        RAISE EXCEPTION 'Expected 5 key constraints for submission_dispatch_outcome, found %.', v_constraints;
    END IF;

    RAISE NOTICE 'PASS: S2W-3.2 submission dispatch outcome table/view and key constraints exist.';
END
$$;
