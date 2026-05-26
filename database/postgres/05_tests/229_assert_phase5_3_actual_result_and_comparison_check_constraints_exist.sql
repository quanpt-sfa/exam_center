-- Verifies expected check constraints exist on Phase 5.3 grading evidence tables.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_gr_ar_result_type',
          'ck_gr_ar_row_count',
          'ck_gr_ar_runtime_ms',
          'ck_gr_eac_comparison_method',
          'ck_gr_eac_comparison_status'
      );

    IF check_count <> 5 THEN
        RAISE EXCEPTION 'Expected 5 check constraints for Phase 5.3 tables but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 check constraints exist.';
END
$$;
