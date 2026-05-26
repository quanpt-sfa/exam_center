-- Phase 3.1.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates exam session runtime core and check-in verification tables.

CREATE TABLE IF NOT EXISTS delivery.exam_session (
    exam_session_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_assignment_id bigint NOT NULL,
    session_code varchar(100) NOT NULL,
    session_no integer NOT NULL DEFAULT 1,
    session_status varchar(30) NOT NULL,
    started_at timestamptz NULL,
    deadline_at timestamptz NULL,
    ended_at timestamptz NULL,
    time_limit_seconds integer NOT NULL,
    extra_time_seconds integer NOT NULL DEFAULT 0,
    last_seen_at timestamptz NULL,
    last_activity_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    created_by bigint NULL,
    CONSTRAINT uq_delivery_exam_session_session_code UNIQUE (session_code),
    CONSTRAINT uq_delivery_exam_session_exam_assignment_session_no UNIQUE (exam_assignment_id, session_no),
    CONSTRAINT ck_delivery_exam_session_status CHECK (
        session_status IN (
            'CREATED',
            'WAITING_FOR_CHECKIN',
            'READY_TO_START',
            'IN_PROGRESS',
            'PAUSED',
            'INTERRUPTED',
            'ENDED',
            'EXPIRED',
            'SUBMITTED',
            'FORCE_CLOSED',
            'VOIDED'
        )
    ),
    CONSTRAINT ck_delivery_exam_session_time_limit_seconds CHECK (time_limit_seconds > 0),
    CONSTRAINT ck_delivery_exam_session_extra_time_seconds CHECK (extra_time_seconds >= 0),
    CONSTRAINT ck_delivery_exam_session_deadline_requires_started CHECK (deadline_at IS NULL OR started_at IS NOT NULL),
    CONSTRAINT ck_delivery_exam_session_ended_requires_started CHECK (ended_at IS NULL OR started_at IS NOT NULL),
    CONSTRAINT ck_delivery_exam_session_ended_after_started CHECK (ended_at IS NULL OR deadline_at IS NULL OR ended_at >= started_at),
    CONSTRAINT ck_delivery_exam_session_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_delivery_exam_session_exam_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_delivery_exam_session_active_per_exam_assignment
    ON delivery.exam_session (exam_assignment_id)
    WHERE session_status IN (
        'CREATED',
        'WAITING_FOR_CHECKIN',
        'READY_TO_START',
        'IN_PROGRESS',
        'PAUSED',
        'INTERRUPTED'
    );

CREATE TABLE IF NOT EXISTS delivery.exam_checkin_verification (
    checkin_verification_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_assignment_id bigint NOT NULL,
    exam_session_id bigint NULL,
    station_assignment_id bigint NULL,
    verified_by bigint NOT NULL,
    verified_at timestamptz NOT NULL DEFAULT now(),
    verification_status varchar(30) NOT NULL,
    verification_method varchar(50) NOT NULL,
    note text NULL,
    metadata_json jsonb NULL,
    CONSTRAINT ck_delivery_exam_checkin_verification_status CHECK (
        verification_status IN ('VERIFIED', 'REJECTED', 'NEEDS_REVIEW', 'CANCELLED')
    ),
    CONSTRAINT ck_delivery_exam_checkin_verification_method CHECK (
        verification_method IN ('PHOTO_ON_SCREEN', 'STUDENT_CARD', 'MANUAL_ID_CHECK', 'ADMIN_OVERRIDE')
    ),
    CONSTRAINT fk_delivery_exam_checkin_verification_exam_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_checkin_verification_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_checkin_verification_station_assignment FOREIGN KEY (station_assignment_id)
        REFERENCES delivery.exam_station_assignment(station_assignment_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_checkin_verification_verified_by FOREIGN KEY (verified_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_exam_assignment_id
    ON delivery.exam_session (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_created_by
    ON delivery.exam_session (created_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_session_status
    ON delivery.exam_session (session_status);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_deadline_at
    ON delivery.exam_session (deadline_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_last_seen_at
    ON delivery.exam_session (last_seen_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_exam_assignment_id
    ON delivery.exam_checkin_verification (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_exam_session_id
    ON delivery.exam_checkin_verification (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_station_assignment_id
    ON delivery.exam_checkin_verification (station_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_checkin_verification_verified_by
    ON delivery.exam_checkin_verification (verified_by);

DO
$$
BEGIN
    -- Backfill conditional Phase 3.0.4 exam_session FKs now that exam_session exists.
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

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_checkin_verification TO exam_sys_app;

-- Restrict broad readonly visibility for operationally sensitive runtime/check-in data.
REVOKE SELECT ON TABLE delivery.exam_session FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_checkin_verification FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
