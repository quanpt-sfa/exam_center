-- Phase 3.1.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Ensures nullable exam_session foreign keys and lookup indexes exist on Phase 3.0 operational tables.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_session_incident_exam_session'
    ) THEN
        ALTER TABLE delivery.exam_session_incident
            ADD CONSTRAINT fk_delivery_exam_session_incident_exam_session
            FOREIGN KEY (exam_session_id)
            REFERENCES delivery.exam_session(exam_session_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_session_transfer_exam_session'
    ) THEN
        ALTER TABLE delivery.exam_session_transfer
            ADD CONSTRAINT fk_delivery_exam_session_transfer_exam_session
            FOREIGN KEY (exam_session_id)
            REFERENCES delivery.exam_session(exam_session_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_reschedule_original_exam_session'
    ) THEN
        ALTER TABLE delivery.exam_reschedule
            ADD CONSTRAINT fk_delivery_exam_reschedule_original_exam_session
            FOREIGN KEY (original_exam_session_id)
            REFERENCES delivery.exam_session(exam_session_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_exam_session_id
    ON delivery.exam_session_incident (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_exam_session_id
    ON delivery.exam_session_transfer (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_reschedule_original_exam_session_id
    ON delivery.exam_reschedule (original_exam_session_id);
