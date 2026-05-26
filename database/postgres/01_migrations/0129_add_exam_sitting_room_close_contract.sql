ALTER TABLE delivery.exam_sitting_room
    ADD COLUMN IF NOT EXISTS closed_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS closed_by bigint NULL,
    ADD COLUMN IF NOT EXISTS close_reason varchar(100) NULL,
    ADD COLUMN IF NOT EXISTS close_note text NULL,
    ADD COLUMN IF NOT EXISTS close_summary_json jsonb NULL,
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS updated_by bigint NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_sitting_room_closed_by'
    ) THEN
        ALTER TABLE delivery.exam_sitting_room
            ADD CONSTRAINT fk_delivery_exam_sitting_room_closed_by
            FOREIGN KEY (closed_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_delivery_exam_sitting_room_updated_by'
    ) THEN
        ALTER TABLE delivery.exam_sitting_room
            ADD CONSTRAINT fk_delivery_exam_sitting_room_updated_by
            FOREIGN KEY (updated_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS delivery.exam_sitting_room_history (
    room_history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_sitting_room_id bigint NOT NULL,
    actor_user_id bigint NULL,
    actor_role varchar(50) NOT NULL,
    action_type varchar(50) NOT NULL,
    from_room_status varchar(30) NULL,
    to_room_status varchar(30) NOT NULL,
    close_reason varchar(100) NULL,
    close_note text NULL,
    close_summary_json jsonb NULL,
    blocker_summary_json jsonb NULL,
    context_json jsonb NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_delivery_exam_sitting_room_history_room
        FOREIGN KEY (exam_sitting_room_id)
        REFERENCES delivery.exam_sitting_room(exam_sitting_room_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_delivery_exam_sitting_room_history_actor_user
        FOREIGN KEY (actor_user_id)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL,
    CONSTRAINT ck_delivery_exam_sitting_room_history_to_room_status
        CHECK (to_room_status IN ('PLANNED', 'READY', 'OPEN', 'CLOSED', 'CANCELLED')),
    CONSTRAINT ck_delivery_exam_sitting_room_history_from_room_status
        CHECK (from_room_status IS NULL OR from_room_status IN ('PLANNED', 'READY', 'OPEN', 'CLOSED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS idx_room_hist_room_changed
    ON delivery.exam_sitting_room_history (exam_sitting_room_id, changed_at DESC, room_history_id DESC);

CREATE INDEX IF NOT EXISTS idx_room_hist_actor_changed
    ON delivery.exam_sitting_room_history (actor_user_id, changed_at DESC, room_history_id DESC)
    WHERE actor_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_room_hist_status_changed
    ON delivery.exam_sitting_room_history (to_room_status, changed_at DESC, room_history_id DESC);

COMMENT ON COLUMN delivery.exam_sitting_room.closed_at IS
    'Timestamp when the room was closed through the room-scoped close-room contract.';

COMMENT ON COLUMN delivery.exam_sitting_room.closed_by IS
    'Actor who closed the room through the room-scoped close-room contract.';

COMMENT ON COLUMN delivery.exam_sitting_room.close_reason IS
    'Backend-authored reason code for the latest room closure action.';

COMMENT ON COLUMN delivery.exam_sitting_room.close_note IS
    'Optional operator note captured at room close time.';

COMMENT ON COLUMN delivery.exam_sitting_room.close_summary_json IS
    'Server-authored close summary captured at successful room close time.';

COMMENT ON TABLE delivery.exam_sitting_room_history IS
    'Immutable audit trail for room lifecycle mutations, including room close actions.';

GRANT SELECT, UPDATE ON TABLE delivery.exam_sitting_room TO exam_sys_app;
GRANT SELECT ON TABLE delivery.exam_sitting_room TO exam_sys_readonly;
GRANT SELECT, INSERT ON TABLE delivery.exam_sitting_room_history TO exam_sys_app;
REVOKE SELECT ON TABLE delivery.exam_sitting_room_history FROM exam_sys_readonly;
GRANT USAGE, SELECT ON SEQUENCE delivery.exam_sitting_room_history_room_history_id_seq TO exam_sys_app;
GRANT USAGE, SELECT ON SEQUENCE delivery.exam_sitting_room_history_room_history_id_seq TO exam_sys_readonly;
