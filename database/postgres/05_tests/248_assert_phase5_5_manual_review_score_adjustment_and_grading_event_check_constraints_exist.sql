-- Verifies expected check constraints exist on Phase 5.5 tables.

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
          'ck_gr_mrq_review_reason',
          'ck_gr_mrq_review_status',
          'ck_gr_mrq_resolved_status',
          'ck_gr_mrq_resolved_by_requires_resolved_at',
          'ck_gr_mrq_updated_at',
          'ck_gr_sa_adjustment_type',
          'ck_gr_sa_target_present',
          'ck_gr_sa_old_score_non_negative',
          'ck_gr_sa_new_score_non_negative',
          'ck_gr_ge_event_type',
          'ck_gr_ge_target_present'
      );

    IF check_count <> 11 THEN
        RAISE EXCEPTION 'Expected 11 check constraints for Phase 5.5 tables but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.5 check constraints exist.';
END
$$;
