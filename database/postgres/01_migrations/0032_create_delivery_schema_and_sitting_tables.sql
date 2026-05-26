-- Phase 3.0.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates delivery schema and foundational exam sitting tables.

CREATE SCHEMA IF NOT EXISTS delivery;

COMMENT ON SCHEMA delivery IS 'Delivery schema: exam sitting, room planning, and proctoring assignments.';

ALTER SCHEMA delivery OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA delivery TO exam_sys_app;
GRANT USAGE ON SCHEMA delivery TO exam_sys_readonly;
GRANT CREATE ON SCHEMA delivery TO exam_sys_owner;

CREATE TABLE IF NOT EXISTS delivery.exam_sitting (
    exam_sitting_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_version_id bigint NOT NULL,
    sitting_code varchar(100) NOT NULL,
    sitting_name varchar(255) NOT NULL,
    scheduled_start_at timestamptz NOT NULL,
    scheduled_end_at timestamptz NOT NULL,
    timezone varchar(100) NULL,
    sitting_status varchar(30) NOT NULL,
    created_by bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NULL,
    CONSTRAINT uq_delivery_exam_sitting_sitting_code UNIQUE (sitting_code),
    CONSTRAINT ck_delivery_exam_sitting_schedule CHECK (scheduled_end_at > scheduled_start_at),
    CONSTRAINT ck_delivery_exam_sitting_status CHECK (
        sitting_status IN ('DRAFT', 'READY', 'OPEN', 'IN_PROGRESS', 'CLOSED', 'CANCELLED', 'ARCHIVED')
    ),
    CONSTRAINT ck_delivery_exam_sitting_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at),
    CONSTRAINT fk_delivery_exam_sitting_exam_version FOREIGN KEY (exam_version_id)
        REFERENCES assessment.exam_version(exam_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_sitting_created_by FOREIGN KEY (created_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS delivery.exam_sitting_room (
    exam_sitting_room_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_id bigint NOT NULL,
    room_id bigint NOT NULL,
    capacity_allocated integer NULL,
    room_status varchar(30) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_delivery_exam_sitting_room_sitting_room UNIQUE (exam_sitting_id, room_id),
    CONSTRAINT ck_delivery_exam_sitting_room_capacity_allocated CHECK (
        capacity_allocated IS NULL OR capacity_allocated >= 0
    ),
    CONSTRAINT ck_delivery_exam_sitting_room_status CHECK (
        room_status IN ('PLANNED', 'READY', 'OPEN', 'CLOSED', 'CANCELLED')
    ),
    CONSTRAINT fk_delivery_exam_sitting_room_exam_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting(exam_sitting_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_sitting_room_room FOREIGN KEY (room_id)
        REFERENCES facility.room(room_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_exam_version_id
    ON delivery.exam_sitting (exam_version_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_created_by
    ON delivery.exam_sitting (created_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_room_exam_sitting_id
    ON delivery.exam_sitting_room (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_room_room_id
    ON delivery.exam_sitting_room (room_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_sitting TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_sitting_room TO exam_sys_app;

GRANT SELECT ON TABLE delivery.exam_sitting TO exam_sys_readonly;
GRANT SELECT ON TABLE delivery.exam_sitting_room TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;