-- Phase 2C-BE: add immutable room-scoped attendance history and widen verification method constraint.

CREATE TABLE IF NOT EXISTS delivery.exam_assignment_attendance_history (
    attendance_history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_assignment_id bigint NOT NULL,
    exam_sitting_room_id bigint NOT NULL,
    station_assignment_id bigint NULL,
    previous_assignment_status varchar(30) NULL,
    new_assignment_status varchar(30) NOT NULL,
    previous_station_status varchar(30) NULL,
    new_station_status varchar(30) NULL,
    actor_user_id bigint NULL,
    actor_role varchar(50) NOT NULL,
    action_type varchar(50) NOT NULL,
    note text NULL,
    context_json jsonb NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_delivery_exam_assignment_attendance_history_assignment FOREIGN KEY (exam_assignment_id)
        REFERENCES delivery.exam_assignment(exam_assignment_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_assignment_attendance_history_room FOREIGN KEY (exam_sitting_room_id)
        REFERENCES delivery.exam_sitting_room(exam_sitting_room_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_delivery_exam_assignment_attendance_history_station_assignment FOREIGN KEY (station_assignment_id)
        REFERENCES delivery.exam_station_assignment(station_assignment_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_delivery_exam_assignment_attendance_history_actor FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_att_hist_assignment_changed
    ON delivery.exam_assignment_attendance_history (exam_assignment_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_att_hist_room_changed
    ON delivery.exam_assignment_attendance_history (exam_sitting_room_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_att_hist_actor_changed
    ON delivery.exam_assignment_attendance_history (actor_user_id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_att_hist_action_changed
    ON delivery.exam_assignment_attendance_history (action_type, changed_at DESC);

DO
$$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_delivery_exam_checkin_verification_method'
          AND conrelid = 'delivery.exam_checkin_verification'::regclass
    ) THEN
        ALTER TABLE delivery.exam_checkin_verification
            DROP CONSTRAINT ck_delivery_exam_checkin_verification_method;
    END IF;

    ALTER TABLE delivery.exam_checkin_verification
        ADD CONSTRAINT ck_delivery_exam_checkin_verification_method CHECK (
            verification_method IN (
                'PHOTO_ON_SCREEN',
                'STUDENT_CARD',
                'MANUAL_ID_CHECK',
                'ADMIN_OVERRIDE',
                'PHOTO_ID',
                'MANUAL',
                'OTHER'
            )
        );
END
$$;

GRANT SELECT, INSERT ON TABLE delivery.exam_assignment_attendance_history TO exam_sys_app;
REVOKE SELECT ON TABLE delivery.exam_assignment_attendance_history FROM exam_sys_readonly;

GRANT USAGE, SELECT ON SEQUENCE delivery.exam_assignment_attendance_history_attendance_history_id_seq TO exam_sys_app;
GRANT USAGE, SELECT ON SEQUENCE delivery.exam_assignment_attendance_history_attendance_history_id_seq TO exam_sys_readonly;