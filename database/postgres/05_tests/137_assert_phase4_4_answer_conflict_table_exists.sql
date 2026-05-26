-- Verifies submission.answer_conflict exists for Phase 4.4.

DO
$$
BEGIN
    IF to_regclass('submission.answer_conflict') IS NULL THEN
        RAISE EXCEPTION 'Missing table: submission.answer_conflict';
    END IF;

    RAISE NOTICE 'PASS: submission.answer_conflict exists.';
END
$$;
