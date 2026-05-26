-- Verifies submission.answer_conflict has a single primary key.

DO
$$
DECLARE
    pk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO pk_count
    FROM pg_constraint c
    WHERE c.contype = 'p'
      AND c.conrelid = to_regclass('submission.answer_conflict');

    IF pk_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 primary key on submission.answer_conflict but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_conflict primary key exists.';
END
$$;
