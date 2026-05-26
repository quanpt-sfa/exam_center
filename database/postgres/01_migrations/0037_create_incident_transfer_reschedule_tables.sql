-- Phase 3.0.4 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates operational incident, station transfer, and exam reschedule tables.

CREATE TABLE IF NOT EXISTS delivery.exam_session_incident (
    incident_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_id bigint NOT NULL,
    exam_assignment_id bigint NULL,
    exam_session_id bigint NULL,
    station_id bigint NULL,
    device_id bigint NULL,
    incident_type varchar(100) NOT NULL,
    incident_status varchar(30) NOT NULL,
    reported_by bigint NULL,
    reported_at timestamptz NOT NULL DEFAULT now(),
    resolved_by bigint NULL,
    resolved_at timestamptz NULL,
    description text NULL,
    metadata_json jsonb NULL,
    CONSTRAINT ck_delivery_exam_session_incident_type CHECK (
        incident_type IN (
            'DEVICE_FAILURE',
            'POWER_FAILURE',
            'NETWORK_FAILURE',
            'DISPLAY_FAILURE',
            'KEYBOARD_MOUSE_FAILURE',
            'LOGIN_ISSUE',
            'IDENTITY_MISMATCH',
            'STUDENT_ILLNESS',
            'ADMIN_NOTE'
        )
    ),
    CONSTRAINT ck_delivery_exam_session_incident_status CHECK (
        incident_status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'VOIDED')
    ),
    CONSTRAINT ck_delivery_exam_session_incident_resolved_at CHECK (
        resolved_at IS NULL OR resolved_at >= reported_at
    ),
    CONSTRAINT fk_delivery_exam_session_incident_exam_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting(exam_sitting_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_incident_exam_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_incident_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_incident_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_incident_reported_by FOREIGN KEY (reported_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_incident_resolved_by FOREIGN KEY (resolved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS delivery.exam_session_transfer (
    session_transfer_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_id bigint NOT NULL,
    exam_assignment_id bigint NOT NULL,
    exam_session_id bigint NULL,
    from_station_id bigint NOT NULL,
    to_station_id bigint NOT NULL,
    from_device_id bigint NULL,
    to_device_id bigint NULL,
    reason_code varchar(100) NOT NULL,
    approved_by bigint NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT now(),
    time_adjustment_seconds integer NOT NULL DEFAULT 0,
    note text NULL,
    CONSTRAINT ck_delivery_exam_session_transfer_station_diff CHECK (from_station_id <> to_station_id),
    CONSTRAINT ck_delivery_exam_session_transfer_time_adjustment CHECK (time_adjustment_seconds >= 0),
    CONSTRAINT ck_delivery_exam_session_transfer_reason_code CHECK (
        reason_code IN (
            'DEVICE_FAILURE',
            'POWER_FAILURE',
            'NETWORK_FAILURE',
            'DISPLAY_FAILURE',
            'KEYBOARD_MOUSE_FAILURE',
            'ADMIN_TRANSFER'
        )
    ),
    CONSTRAINT fk_delivery_exam_session_transfer_exam_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting(exam_sitting_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_transfer_exam_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_transfer_from_station FOREIGN KEY (from_station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_transfer_to_station FOREIGN KEY (to_station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_transfer_from_device FOREIGN KEY (from_device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_transfer_to_device FOREIGN KEY (to_device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_transfer_approved_by FOREIGN KEY (approved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS delivery.exam_reschedule (
    reschedule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    original_exam_assignment_id bigint NOT NULL,
    new_exam_assignment_id bigint NULL,
    original_exam_session_id bigint NULL,
    reason_code varchar(100) NOT NULL,
    approved_by bigint NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT now(),
    policy_code varchar(100) NULL,
    note text NULL,
    status varchar(30) NOT NULL,
    CONSTRAINT ck_delivery_exam_reschedule_reason_code CHECK (
        reason_code IN (
            'DEVICE_FAILURE_UNRECOVERABLE',
            'POWER_OUTAGE',
            'NETWORK_OUTAGE',
            'HEALTH_INCIDENT',
            'ADMIN_DECISION'
        )
    ),
    CONSTRAINT ck_delivery_exam_reschedule_status CHECK (
        status IN ('REQUESTED', 'APPROVED', 'SCHEDULED', 'COMPLETED', 'CANCELLED', 'REJECTED')
    ),
    CONSTRAINT ck_delivery_exam_reschedule_new_assignment CHECK (
        new_exam_assignment_id IS NULL OR new_exam_assignment_id <> original_exam_assignment_id
    ),
    CONSTRAINT fk_delivery_exam_reschedule_original_exam_assignment FOREIGN KEY (original_exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_reschedule_new_exam_assignment FOREIGN KEY (new_exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_reschedule_approved_by FOREIGN KEY (approved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

DO
$$
BEGIN
    -- Add exam_session FK constraints only when delivery.exam_session exists.
    IF to_regclass('delivery.exam_session') IS NOT NULL THEN
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
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_exam_sitting_id
    ON delivery.exam_session_incident (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_exam_assignment_id
    ON delivery.exam_session_incident (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_station_id
    ON delivery.exam_session_incident (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_device_id
    ON delivery.exam_session_incident (device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_reported_by
    ON delivery.exam_session_incident (reported_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_incident_resolved_by
    ON delivery.exam_session_incident (resolved_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_exam_sitting_id
    ON delivery.exam_session_transfer (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_exam_assignment_id
    ON delivery.exam_session_transfer (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_from_station_id
    ON delivery.exam_session_transfer (from_station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_to_station_id
    ON delivery.exam_session_transfer (to_station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_transfer_approved_by
    ON delivery.exam_session_transfer (approved_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_reschedule_original_exam_assignment_id
    ON delivery.exam_reschedule (original_exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_reschedule_new_exam_assignment_id
    ON delivery.exam_reschedule (new_exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_reschedule_approved_by
    ON delivery.exam_reschedule (approved_by);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session_incident TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session_transfer TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_reschedule TO exam_sys_app;

-- Restrict broad readonly exposure for sensitive operational records.
REVOKE SELECT ON TABLE delivery.exam_session_incident FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_transfer FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_reschedule FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
