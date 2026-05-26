-- Verifies grading.question_grading_task exists for Phase 5.2.

DO
$$
BEGIN
    IF to_regclass('grading.question_grading_task') IS NULL THEN
        RAISE EXCEPTION 'Table grading.question_grading_task does not exist';
    END IF;

    RAISE NOTICE 'PASS: grading.question_grading_task exists.';
END
$$;
