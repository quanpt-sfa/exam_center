ALTER TABLE delivery.exam_session_incident
    ADD COLUMN IF NOT EXISTS exam_sitting_room_id bigint NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_session_incident_exam_sitting_room'
    ) THEN
        ALTER TABLE delivery.exam_session_incident
            ADD CONSTRAINT fk_delivery_exam_session_incident_exam_sitting_room
            FOREIGN KEY (exam_sitting_room_id)
            REFERENCES delivery.exam_sitting_room(exam_sitting_room_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_room_reported_at_desc
    ON delivery.exam_session_incident (exam_sitting_room_id, reported_at DESC, incident_id DESC);
