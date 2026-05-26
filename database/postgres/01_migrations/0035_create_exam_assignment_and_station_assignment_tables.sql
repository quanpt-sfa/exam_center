-- Phase 3.0.3 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates student exam assignment and station seating assignment tables.

CREATE TABLE IF NOT EXISTS delivery.exam_assignment (
    exam_assignment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_id bigint NOT NULL,
    student_id bigint NOT NULL,
    assignment_status varchar(30) NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    assigned_by bigint NULL,
    note text NULL,
    CONSTRAINT uq_delivery_exam_assignment_sitting_student UNIQUE (exam_sitting_id, student_id),
    CONSTRAINT ck_delivery_exam_assignment_status CHECK (
        assignment_status IN ('ASSIGNED', 'CHECKED_IN', 'ABSENT', 'CANCELLED', 'RESCHEDULED', 'VOIDED', 'COMPLETED')
    ),
    CONSTRAINT fk_delivery_exam_assignment_exam_sitting FOREIGN KEY (exam_sitting_id)
        REFERENCES delivery.exam_sitting(exam_sitting_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_assignment_student FOREIGN KEY (student_id)
        REFERENCES identity.student_profile(student_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_assignment_assigned_by FOREIGN KEY (assigned_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS delivery.exam_station_assignment (
    station_assignment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_assignment_id bigint NOT NULL,
    exam_sitting_room_id bigint NOT NULL,
    station_id bigint NOT NULL,
    planned_device_id bigint NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    assigned_by bigint NULL,
    status varchar(30) NOT NULL,
    CONSTRAINT uq_delivery_exam_station_assignment_exam_assignment UNIQUE (exam_assignment_id),
    CONSTRAINT uq_delivery_exam_station_assignment_room_station UNIQUE (exam_sitting_room_id, station_id),
    CONSTRAINT ck_delivery_exam_station_assignment_status CHECK (
        status IN ('ASSIGNED', 'CHECKED_IN', 'TRANSFERRED', 'CANCELLED', 'NO_SHOW')
    ),
    CONSTRAINT fk_delivery_exam_station_assignment_exam_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_station_assignment_exam_sitting_room FOREIGN KEY (exam_sitting_room_id)
        REFERENCES delivery.exam_sitting_room(exam_sitting_room_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_station_assignment_station FOREIGN KEY (station_id)
        REFERENCES facility.lab_station(station_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_station_assignment_planned_device FOREIGN KEY (planned_device_id)
        REFERENCES facility.device(device_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_station_assignment_assigned_by FOREIGN KEY (assigned_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_assignment_exam_sitting_id
    ON delivery.exam_assignment (exam_sitting_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_assignment_student_id
    ON delivery.exam_assignment (student_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_assignment_assigned_by
    ON delivery.exam_assignment (assigned_by);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_exam_assignment_id
    ON delivery.exam_station_assignment (exam_assignment_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_exam_sitting_room_id
    ON delivery.exam_station_assignment (exam_sitting_room_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_station_id
    ON delivery.exam_station_assignment (station_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_planned_device_id
    ON delivery.exam_station_assignment (planned_device_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_assigned_by
    ON delivery.exam_station_assignment (assigned_by);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_assignment TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.exam_station_assignment TO exam_sys_app;

GRANT SELECT ON TABLE delivery.exam_assignment TO exam_sys_readonly;

-- Restrict broad readonly visibility for detailed seating plan operations.
REVOKE SELECT ON TABLE delivery.exam_station_assignment FROM exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;
