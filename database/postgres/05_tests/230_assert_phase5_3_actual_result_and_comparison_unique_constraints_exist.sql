-- Verifies expected unique constraints exist on Phase 5.3 grading evidence tables.

DO
$$
DECLARE
    uniq_count integer;
BEGIN
    SELECT COUNT(*)
    INTO uniq_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_gr_ar_question_task',
          'uq_gr_eac_question_task'
      );

    IF uniq_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 unique constraints for Phase 5.3 tables but found %', uniq_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 unique constraints exist.';
END
$$;
