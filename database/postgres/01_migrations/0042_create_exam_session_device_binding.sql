-- Phase 3.1.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates session-device binding table for runtime session station/device ownership.

CREATE TABLE IF NOT EXISTS delivery.exam_session_device_binding (
    session_device_binding_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_session_id bigint NOT NULL,
    exam_sitting_id bigint NOT NULL,
    station_id bigint NOT NULL,
    device_id bigint NULL,
    binding_status varchar(30) NOT NULL,
    bound_at timestamptz NOT NULL DEFAULT now(),
    unbound_at timestamptz NULL,
    ip_address inet NULL,
    hostname varchar(255) NULL,
    client_fingerprint varchar(500) NULL,
    bind_reason varchar(100) NOT NULL,
    metadata_json jsonb NULL,
    CONSTRAINT ck_delivery_exam_session_device_binding_status CHECK (
        binding_status IN ('ACTIVE', 'TRANSFERRED', 'ENDED', 'INVALIDATED')
    ),
    CONSTRAINT ck_delivery_exam_session_device_binding_reason CHECK (
        bind_reason IN ('INITIAL_START', 'RECONNECT', 'DEVICE_TRANSFER', 'ADMIN_OVERRIDE', 'RECOVERY')
    ),
    CONSTRAINT ck_delivery_exam_session_device_binding_unbound_at CHECK (
        unbound_at IS NULL OR unbound_at >= bound_at
    ),
    CONSTRAINT fk_delivery_exam_session_device_binding_exam_session FOREIGN KEY (exam_session_id)
        REFERENCES delivery.exam_session(exam_session_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_device_binding_exam_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting(exam_sitting_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_device_binding_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_session_device_binding_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL
);

COMMENT ON TABLE delivery.exam_session_device_binding IS
'Tracks active/inactive station/device ownership for an exam session. Transfer must close old ACTIVE binding and create a new ACTIVE binding for the same exam_session; it must not create a new exam or generated exam instance.';

COMMENT ON COLUMN delivery.exam_session_device_binding.exam_sitting_id IS
'Cross-table consistency (exam_sitting_id aligned with exam_session -> exam_assignment -> exam_sitting) is expected but intentionally not enforced by SQL in this phase.';

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_exam_session_id
    ON delivery.exam_session_device_binding (exam_session_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_exam_sitting_id
    ON delivery.exam_session_device_binding (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_station_id
    ON delivery.exam_session_device_binding (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_device_id
    ON delivery.exam_session_device_binding (device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_binding_status
    ON delivery.exam_session_device_binding (binding_status);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_session_device_binding_bound_at
    ON delivery.exam_session_device_binding (bound_at);

CREATE UNIQUE INDEX IF NOT EXISTS ux_delivery_exam_session_device_binding_active_per_session
    ON delivery.exam_session_device_binding (exam_session_id)
    WHERE binding_status = 'ACTIVE';

CREATE UNIQUE INDEX IF NOT EXISTS ux_del_exam_sess_dev_bind_active_sit_station
    ON delivery.exam_session_device_binding (exam_sitting_id, station_id)
    WHERE binding_status = 'ACTIVE';

CREATE UNIQUE INDEX IF NOT EXISTS ux_del_exam_sess_dev_bind_active_sit_device
    ON delivery.exam_session_device_binding (exam_sitting_id, device_id)
    WHERE binding_status = 'ACTIVE' AND device_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_session_device_binding TO exam_sys_app;

-- Restrict sensitive endpoint fingerprint and metadata data from broad readonly role.
REVOKE SELECT ON TABLE delivery.exam_session_device_binding FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
