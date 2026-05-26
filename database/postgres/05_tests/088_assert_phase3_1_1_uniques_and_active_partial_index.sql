-- Verifies unique constraints and active partial unique index for exam_session.

DO
$$
DECLARE
    unique_constraint_count integer;
    partial_unique_index_count integer;
BEGIN
    SELECT COUNT(*)
    INTO unique_constraint_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_delivery_exam_session_session_code',
          'uq_delivery_exam_session_exam_assignment_session_no'
      );

    IF unique_constraint_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 unique constraints for exam_session but found %', unique_constraint_count;
    END IF;

    SELECT COUNT(*)
    INTO partial_unique_index_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname = 'ux_delivery_exam_session_active_per_exam_assignment'
      AND i.indexdef ILIKE '%UNIQUE%'
      AND i.indexdef ILIKE '%WHERE%session_status%CREATED%'
      AND i.indexdef ILIKE '%WAITING_FOR_CHECKIN%'
      AND i.indexdef ILIKE '%READY_TO_START%'
      AND i.indexdef ILIKE '%IN_PROGRESS%'
      AND i.indexdef ILIKE '%PAUSED%'
      AND i.indexdef ILIKE '%INTERRUPTED%';

    IF partial_unique_index_count <> 1 THEN
        RAISE EXCEPTION 'Missing or invalid active partial unique index on delivery.exam_session(exam_assignment_id)';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1.1 unique constraints and active partial unique index exist.';
END
$$;
