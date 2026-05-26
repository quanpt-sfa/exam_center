-- Verifies Phase 5.4 score tables exist.

DO
$$
BEGIN
    IF to_regclass('grading.question_score') IS NULL THEN
        RAISE EXCEPTION 'Table grading.question_score does not exist';
    END IF;

    IF to_regclass('grading.submission_score') IS NULL THEN
        RAISE EXCEPTION 'Table grading.submission_score does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.4 score tables exist.';
END
$$;
