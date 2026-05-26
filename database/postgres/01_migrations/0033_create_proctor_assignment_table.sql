-- Phase 3.0.2 source: docs/phase_3_0_facility_proctoring_foundation.md
-- Creates proctor assignment table for exam sitting rooms.

CREATE TABLE IF NOT EXISTS delivery.proctor_assignment (
    proctor_assignment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_room_id bigint NOT NULL,
    proctor_user_id bigint NOT NULL,
    proctor_role varchar(50) NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    assigned_by bigint NULL,
    status varchar(30) NOT NULL,
    CONSTRAINT uq_delivery_proctor_assignment_room_user_role UNIQUE (
        exam_sitting_room_id,
        proctor_user_id,
        proctor_role
    ),
    CONSTRAINT ck_delivery_proctor_assignment_role CHECK (
        proctor_role IN ('HEAD_PROCTOR', 'ROOM_PROCTOR', 'SUPPORT_STAFF', 'TECH_SUPPORT')
    ),
    CONSTRAINT ck_delivery_proctor_assignment_status CHECK (
        status IN ('ASSIGNED', 'CONFIRMED', 'CANCELLED')
    ),
    CONSTRAINT fk_delivery_proctor_assignment_exam_sitting_room FOREIGN KEY (exam_sitting_room_id)
        REFERENCES delivery.exam_sitting_room(exam_sitting_room_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_proctor_assignment_proctor_user FOREIGN KEY (proctor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_proctor_assignment_assigned_by FOREIGN KEY (assigned_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_delivery_proctor_assignment_exam_sitting_room_id
    ON delivery.proctor_assignment (exam_sitting_room_id);

CREATE INDEX IF NOT EXISTS idx_delivery_proctor_assignment_proctor_user_id
    ON delivery.proctor_assignment (proctor_user_id);

CREATE INDEX IF NOT EXISTS idx_delivery_proctor_assignment_assigned_by
    ON delivery.proctor_assignment (assigned_by);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE delivery.proctor_assignment TO exam_sys_app;
GRANT SELECT ON TABLE delivery.proctor_assignment TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA delivery TO exam_sys_readonly;