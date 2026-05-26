-- Verifies FK attachments and indexes from operational tables to delivery.exam_session.

DO
$$
DECLARE
    fk_count integer;
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_delivery_exam_session_incident_exam_session',
          'fk_delivery_exam_session_transfer_exam_session',
          'fk_delivery_exam_reschedule_original_exam_session'
      );

    IF fk_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 operational FK attachments to delivery.exam_session, found %', fk_count;
    END IF;

    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname IN (
          'idx_delivery_exam_session_incident_exam_session_id',
          'idx_delivery_exam_session_transfer_exam_session_id',
          'idx_delivery_exam_reschedule_original_exam_session_id'
      );

    IF idx_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 operational exam_session indexes, found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Operational FK attachments and indexes to delivery.exam_session exist.';
END
$$;
