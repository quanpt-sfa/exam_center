-- Phase 3.0.1 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates facility schema and foundational room/station tables.

CREATE SCHEMA IF NOT EXISTS facility;

COMMENT ON SCHEMA facility IS 'Facility domain schema: rooms, stations, devices, and readiness check-ins.';

ALTER SCHEMA facility OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA facility TO exam_sys_app;
GRANT USAGE ON SCHEMA facility TO exam_sys_readonly;
GRANT CREATE ON SCHEMA facility TO exam_sys_owner;

CREATE TABLE IF NOT EXISTS facility.room (
    room_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_code varchar(100) NOT NULL,
    room_name varchar(255) NOT NULL,
    building varchar(255) NULL,
    floor_no varchar(50) NULL,
    capacity integer NULL,
    room_type varchar(50) NOT NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_facility_room_room_code UNIQUE (room_code),
    CONSTRAINT ck_facility_room_capacity CHECK (capacity IS NULL OR capacity >= 0),
    CONSTRAINT ck_facility_room_type CHECK (room_type IN ('LAB', 'CLASSROOM', 'ONLINE', 'HYBRID')),
    CONSTRAINT ck_facility_room_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE', 'ARCHIVED')),
    CONSTRAINT ck_facility_room_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS facility.lab_station (
    station_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id bigint NOT NULL,
    station_code varchar(100) NOT NULL,
    seat_no varchar(50) NULL,
    row_no varchar(50) NULL,
    column_no varchar(50) NULL,
    status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_facility_lab_station_room_station_code UNIQUE (room_id, station_code),
    CONSTRAINT ck_facility_lab_station_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'MAINTENANCE', 'RESERVED')),
    CONSTRAINT ck_facility_lab_station_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_facility_lab_station_room FOREIGN KEY (room_id)
        REFERENCES facility.room(room_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_facility_lab_station_room_id
    ON facility.lab_station (room_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE facility.room TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE facility.lab_station TO exam_sys_app;

GRANT SELECT ON TABLE facility.room TO exam_sys_readonly;
GRANT SELECT ON TABLE facility.lab_station TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA facility TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA facility TO exam_sys_readonly;
