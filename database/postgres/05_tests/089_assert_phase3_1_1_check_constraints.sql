-- Verifies key check constraints for exam session and check-in verification.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_delivery_exam_session_status',
          'ck_delivery_exam_session_time_limit_seconds',
          'ck_delivery_exam_session_extra_time_seconds',
          'ck_delivery_exam_session_deadline_requires_started',
          'ck_delivery_exam_session_ended_requires_started',
          'ck_delivery_exam_session_ended_after_started',
          'ck_delivery_exam_checkin_verification_status',
          'ck_delivery_exam_checkin_verification_method'
      );

    IF expected_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 key check constraints for Phase 3.1.1 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1.1 check constraints exist.';
END
$$;
