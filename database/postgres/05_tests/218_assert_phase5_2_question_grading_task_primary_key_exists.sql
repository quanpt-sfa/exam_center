-- Verifies primary key exists on grading.question_grading_task.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'grading.question_grading_task'::regclass
          AND c.contype = 'p'
    ) THEN
        RAISE EXCEPTION 'Primary key missing on grading.question_grading_task';
    END IF;

    RAISE NOTICE 'PASS: grading.question_grading_task primary key exists.';
END
$$;
