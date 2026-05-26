-- Verifies Phase 5.5 tables exist.

DO
$$
BEGIN
    IF to_regclass('grading.manual_review_queue') IS NULL THEN
        RAISE EXCEPTION 'Table grading.manual_review_queue does not exist';
    END IF;

    IF to_regclass('grading.score_adjustment') IS NULL THEN
        RAISE EXCEPTION 'Table grading.score_adjustment does not exist';
    END IF;

    IF to_regclass('grading.grading_event') IS NULL THEN
        RAISE EXCEPTION 'Table grading.grading_event does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.5 tables exist.';
END
$$;
