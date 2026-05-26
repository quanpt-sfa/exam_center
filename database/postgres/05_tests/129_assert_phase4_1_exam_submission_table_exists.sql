-- Verifies submission.exam_submission exists for Phase 4.1.

DO
$$
BEGIN
    IF to_regclass('submission.exam_submission') IS NULL THEN
        RAISE EXCEPTION 'Missing table: submission.exam_submission';
    END IF;

    RAISE NOTICE 'PASS: submission.exam_submission exists.';
END
$$;
