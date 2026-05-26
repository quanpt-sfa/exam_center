-- Verifies submission.exam_submission has a single primary key.

DO
$$
DECLARE
    pk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO pk_count
    FROM pg_constraint c
    WHERE c.contype = 'p'
      AND c.conrelid = to_regclass('submission.exam_submission');

    IF pk_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 primary key on submission.exam_submission but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: submission.exam_submission primary key exists.';
END
$$;
