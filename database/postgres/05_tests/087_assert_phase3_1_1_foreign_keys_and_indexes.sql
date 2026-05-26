-- Verifies Phase 3.1.1 foreign keys and required indexes.

DO
$$
DECLARE
    expected_fk_count integer;
    expected_index_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_delivery_exam_session_exam_assignment',
          'fk_delivery_exam_session_created_by',
          'fk_delivery_exam_checkin_verification_exam_assignment',
          'fk_delivery_exam_checkin_verification_exam_session',
          'fk_delivery_exam_checkin_verification_station_assignment',
          'fk_delivery_exam_checkin_verification_verified_by'
      );

    IF expected_fk_count <> 6 THEN
        RAISE EXCEPTION 'Expected 6 foreign keys for Phase 3.1.1 but found %', expected_fk_count;
    END IF;

    SELECT COUNT(*)
    INTO expected_index_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname IN (
          'idx_delivery_exam_session_exam_assignment_id',
          'idx_delivery_exam_session_created_by',
          'idx_delivery_exam_session_session_status',
          'idx_delivery_exam_session_deadline_at',
          'idx_delivery_exam_session_last_seen_at',
          'idx_delivery_exam_checkin_verification_exam_assignment_id',
          'idx_delivery_exam_checkin_verification_exam_session_id',
          'idx_delivery_exam_checkin_verification_station_assignment_id',
          'idx_delivery_exam_checkin_verification_verified_by'
      );

    IF expected_index_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 indexes for Phase 3.1.1 but found %', expected_index_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1.1 foreign keys and required indexes exist.';
END
$$;
