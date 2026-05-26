-- Phase 3.0.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates facility device registry and check-in tables.

CREATE TABLE IF NOT EXISTS facility.device (
    device_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_tag varchar(100) NOT NULL,
    device_name varchar(255) NULL,
    device_type varchar(50) NOT NULL,
    serial_no varchar(255) NULL,
    current_station_id bigint NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_facility_device_asset_tag UNIQUE (asset_tag),
    CONSTRAINT ck_facility_device_type CHECK (device_type IN ('LAB_PC', 'LAPTOP', 'TABLET', 'SERVER')),
    CONSTRAINT ck_facility_device_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE', 'RETIRED', 'LOST')),
    CONSTRAINT ck_facility_device_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_facility_device_current_station FOREIGN KEY (current_station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS facility.device_registration (
    device_registration_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id bigint NOT NULL,
    registration_type varchar(50) NOT NULL,
    registration_value varchar(500) NOT NULL,
    valid_from timestamptz NOT NULL DEFAULT now(),
    valid_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_facility_device_registration_type CHECK (
        registration_type IN (
            'HOSTNAME',
            'MAC_ADDRESS',
            'WINDOWS_MACHINE_GUID',
            'BROWSER_KIOSK_TOKEN',
            'IP_ALLOWLIST',
            'CLIENT_CERT_FINGERPRINT'
        )
    ),
    CONSTRAINT ck_facility_device_registration_valid_range CHECK (valid_to IS NULL OR valid_to > valid_from),
    CONSTRAINT fk_facility_device_registration_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS facility.device_checkin (
    device_checkin_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id bigint NOT NULL,
    station_id bigint NULL,
    checkin_at timestamptz NOT NULL DEFAULT now(),
    ip_address inet NULL,
    hostname varchar(255) NULL,
    client_fingerprint varchar(500) NULL,
    health_status varchar(30) NOT NULL,
    metadata_json jsonb NULL,
    CONSTRAINT ck_facility_device_checkin_health_status CHECK (health_status IN ('READY', 'WARNING', 'ERROR', 'OFFLINE', 'UNKNOWN')),
    CONSTRAINT fk_facility_device_checkin_device FOREIGN KEY (device_id)
        REFERENCES facility.device(device_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_facility_device_checkin_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_facility_device_registration_active_type_value
    ON facility.device_registration (registration_type, registration_value)
    WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_facility_device_current_station_id
    ON facility.device (current_station_id);

CREATE INDEX IF NOT EXISTS idx_facility_device_registration_device_id
    ON facility.device_registration (device_id);

CREATE INDEX IF NOT EXISTS idx_facility_device_checkin_device_id
    ON facility.device_checkin (device_id);

CREATE INDEX IF NOT EXISTS idx_facility_device_checkin_station_id
    ON facility.device_checkin (station_id);

CREATE INDEX IF NOT EXISTS idx_facility_device_checkin_checkin_at
    ON facility.device_checkin (checkin_at);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE facility.device TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE facility.device_registration TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE facility.device_checkin TO exam_sys_app;

GRANT SELECT ON TABLE facility.device TO exam_sys_readonly;
GRANT SELECT ON TABLE facility.device_checkin TO exam_sys_readonly;

-- Restrict direct exposure of device registration values for readonly role.
REVOKE SELECT ON TABLE facility.device_registration FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA facility TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA facility TO exam_sys_readonly;
