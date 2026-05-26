-- Verifies expected foreign keys exist on Phase 5.3 grading evidence tables.

DO
$$
DECLARE
    fk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_gr_ar_question_task',
          'fk_gr_eac_question_task',
          'fk_gr_eac_expected_answer',
          'fk_gr_eac_actual_result'
      );

    IF fk_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 foreign keys for Phase 5.3 tables but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 foreign keys exist.';
END
$$;
