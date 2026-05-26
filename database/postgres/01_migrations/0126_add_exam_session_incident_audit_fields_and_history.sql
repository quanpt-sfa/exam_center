ALTER TABLE delivery.exam_session_incident
    ADD COLUMN IF NOT EXISTS updated_by bigint NULL,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS resolution_note text NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_session_incident_updated_by'
    ) THEN
        ALTER TABLE delivery.exam_session_incident
            ADD CONSTRAINT fk_delivery_exam_session_incident_updated_by
            FOREIGN KEY (updated_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS delivery.exam_session_incident_history (
    incident_history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id bigint NOT NULL,
    actor_user_id bigint NULL,
    actor_role varchar(50) NOT NULL,
    action_type varchar(50) NOT NULL,
    from_status varchar(30) NULL,
    to_status varchar(30) NULL,
    description_before text NULL,
    description_after text NULL,
    resolution_note text NULL,
    metadata_before jsonb NULL,
    metadata_after jsonb NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    context_json jsonb NULL,
    CONSTRAINT fk_delivery_exam_session_incident_history_incident
        FOREIGN KEY (incident_id)
        REFERENCES delivery.exam_session_incident(incident_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_delivery_exam_session_incident_history_actor_user
        FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_history_incident_changed_at_desc
    ON delivery.exam_session_incident_history (incident_id, changed_at DESC, incident_history_id DESC);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_history_actor_user_changed_at_desc
    ON delivery.exam_session_incident_history (actor_user_id, changed_at DESC, incident_history_id DESC)
    WHERE actor_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_history_to_status_changed_at_desc
    ON delivery.exam_session_incident_history (to_status, changed_at DESC, incident_history_id DESC)
    WHERE to_status IS NOT NULL;

COMMENT ON COLUMN delivery.exam_session_incident.updated_by IS
    'Most recent actor who changed incident status, description, metadata, or resolution note.';

COMMENT ON COLUMN delivery.exam_session_incident.updated_at IS
    'Timestamp of the most recent incident mutation performed through the delivery API.';

COMMENT ON COLUMN delivery.exam_session_incident.resolution_note IS
    'Dedicated closure note captured when an incident transitions to RESOLVED.';

COMMENT ON TABLE delivery.exam_session_incident_history IS
    'Immutable audit trail of incident status, description, resolution note, and metadata changes.';