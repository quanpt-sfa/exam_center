-- Verifies key check constraints for submission.answer_conflict.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_submission_answer_conflict_client_version',
          'ck_submission_answer_conflict_server_version',
          'ck_submission_answer_conflict_resolved_at',
          'ck_submission_answer_conflict_type',
          'ck_submission_answer_conflict_resolved_status'
      );

    IF check_count <> 5 THEN
        RAISE EXCEPTION 'Expected 5 Phase 4.4 check constraints on submission.answer_conflict but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_conflict check constraints exist.';
END
$$;
