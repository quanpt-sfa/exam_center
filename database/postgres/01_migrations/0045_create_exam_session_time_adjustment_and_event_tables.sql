-- Phase 3.1.3 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates exam session time adjustment and lightweight event timeline tables.

CREATE TABLE IF NOT EXISTS delivery.exam_session_time_adjustment (
    time_adjustment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    adjustment_seconds integer NOT NULL,
    old_deadline_at timestamptz NULL,
    new_deadline_at timestamptz NULL,
    reason_code varchar(100) NOT NULL,
    approved_by bigint NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT now(),
    applied_at timestamptz NULL,
    note text NULL,
    metadata_json jsonb NULL,
    CONSTRAINT ck_delivery_exam_session_time_adjustment_seconds CHECK (adjustment_seconds > 0),
    CONSTRAINT ck_delivery_exam_session_time_adjustment_deadline_order CHECK (
        new_deadline_at IS NULL OR old_deadline_at IS NULL OR new_deadline_at > old_deadline_at
    ),
    CONSTRAINT ck_delivery_exam_session_time_adjustment_reason CHECK (
        reason_code IN (
            'DEVICE_FAILURE',
            'POWER_FAILURE',
            'NETWORK_FAILURE',
            'PROCTOR_PAUSE',
            'ADMIN_DECISION',
            'ACCESSIBILITY_ACCOMMODATION',
            'OTHER'
        )
    ),
    CONSTRAINT fk_delivery_exam_session_time_adjustment_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_time_adjustment_approved_by FOREIGN KEY (approved_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS delivery.exam_session_event (
    session_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    event_type varchar(100) NOT NULL,
    event_at timestamptz NOT NULL DEFAULT now(),
    actor_user_id bigint NULL,
    station_id bigint NULL,
    device_id bigint NULL,
    event_payload_json jsonb NULL,
    CONSTRAINT ck_delivery_exam_session_event_type CHECK (
        event_type IN (
            'SESSION_CREATED',
            'STUDENT_CHECKED_IN',
            'PROCTOR_VERIFIED',
            'SESSION_STARTED',
            'SESSION_PAUSED',
            'SESSION_RESUMED',
            'DEVICE_BOUND',
            'DEVICE_TRANSFERRED',
            'TIME_ADJUSTED',
            'SESSION_EXPIRED',
            'SESSION_SUBMITTED',
            'SESSION_FORCE_CLOSED',
            'SESSION_ENDED',
            'SESSION_VOIDED'
        )
    ),
    CONSTRAINT fk_delivery_exam_session_event_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_event_actor_user FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_event_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_session_event_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE delivery.exam_session_time_adjustment IS
'Auditable approvals that adjust authoritative delivery.exam_session.deadline_at. Service layer should apply adjustment insertion, deadline update, and event insertion atomically.';

COMMENT ON TABLE delivery.exam_session_event IS
'Lightweight state transition timeline for exam sessions. Not intended for per-second heartbeat persistence.';

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_time_adjustment_exam_session_id
    ON delivery.exam_session_time_adjustment (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_time_adjustment_approved_by
    ON delivery.exam_session_time_adjustment (approved_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_time_adjustment_approved_at
    ON delivery.exam_session_time_adjustment (approved_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_exam_session_id
    ON delivery.exam_session_event (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_event_type
    ON delivery.exam_session_event (event_type);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_event_at
    ON delivery.exam_session_event (event_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_actor_user_id
    ON delivery.exam_session_event (actor_user_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_station_id
    ON delivery.exam_session_event (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_event_device_id
    ON delivery.exam_session_event (device_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session_time_adjustment TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session_event TO exam_sys_app;

-- Restrict sensitive operational note/payload visibility for broad readonly role.
REVOKE SELECT ON TABLE delivery.exam_session_time_adjustment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_event FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
