-- Verifies expected check constraints exist on Phase 5.4 score tables.

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
          'ck_gr_qs_score_status',
          'ck_gr_qs_raw_score_non_negative',
          'ck_gr_qs_max_score_positive',
          'ck_gr_qs_raw_not_exceed_max',
          'ck_gr_qs_score_percent_non_negative',
          'ck_gr_qs_updated_at',
          'ck_gr_ss_score_status',
          'ck_gr_ss_version_positive',
          'ck_gr_ss_total_raw_non_negative',
          'ck_gr_ss_total_max_non_negative',
          'ck_gr_ss_final_score_non_negative',
          'ck_gr_ss_finalized_at_requires_status',
          'ck_gr_ss_updated_at'
      );

    IF check_count <> 13 THEN
        RAISE EXCEPTION 'Expected 13 check constraints for Phase 5.4 tables but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.4 check constraints exist.';
END
$$;
