-- Phase 3.0 alignment hardening:
-- - enforce delivery.exam_station_assignment station-room integrity
-- - add operational indexes for facility/proctoring lookup paths

-- 1) Cross-table integrity guard:
--    station_id in delivery.exam_station_assignment must belong to
--    the same room as exam_sitting_room.room_id.
CREATE OR REPLACE FUNCTION delivery.fn_validate_exam_station_assignment_room_match()
RETURNS trigger
LANGUAGE plpgsql
AS
$$
DECLARE
    v_room_from_sitting_room bigint;
    v_room_from_station bigint;
BEGIN
    SELECT esr.room_id
    INTO v_room_from_sitting_room
    FROM delivery.exam_sitting_room esr
    WHERE esr.exam_sitting_room_id = NEW.exam_sitting_room_id;

    SELECT ls.room_id
    INTO v_room_from_station
    FROM facility.lab_station ls
    WHERE ls.station_id = NEW.station_id;

    IF v_room_from_sitting_room IS NULL OR v_room_from_station IS NULL THEN
        RETURN NEW;
    END IF;

    IF v_room_from_sitting_room <> v_room_from_station THEN
        RAISE EXCEPTION
            USING
                ERRCODE = '23514',
                MESSAGE = 'station_id does not belong to exam_sitting_room.room_id',
                DETAIL = format(
                    'exam_sitting_room_id=%s room_id=%s, station_id=%s room_id=%s',
                    NEW.exam_sitting_room_id,
                    v_room_from_sitting_room,
                    NEW.station_id,
                    v_room_from_station
                );
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validate_exam_station_assignment_room_match ON delivery.exam_station_assignment;

CREATE TRIGGER trg_validate_exam_station_assignment_room_match
BEFORE INSERT OR UPDATE OF exam_sitting_room_id, station_id
ON delivery.exam_station_assignment
FOR EACH ROW
EXECUTE FUNCTION delivery.fn_validate_exam_station_assignment_room_match();

-- 2) Additional operational indexes for frequent filters.
CREATE INDEX IF NOT EXISTS idx_facility_room_room_code
    ON facility.room (room_code);

CREATE INDEX IF NOT EXISTS idx_facility_lab_station_room_status
    ON facility.lab_station (room_id, status);

CREATE INDEX IF NOT EXISTS idx_facility_device_current_station_status
    ON facility.device (current_station_id, status);

CREATE INDEX IF NOT EXISTS idx_facility_device_status
    ON facility.device (status);

CREATE INDEX IF NOT EXISTS idx_facility_device_registration_active_lookup
    ON facility.device_registration (registration_type, registration_value)
    WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_facility_device_checkin_device_latest
    ON facility.device_checkin (device_id, checkin_at DESC);

CREATE INDEX IF NOT EXISTS idx_facility_device_checkin_station_latest
    ON facility.device_checkin (station_id, checkin_at DESC);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_exam_version_status_time
    ON delivery.exam_sitting (exam_version_id, sitting_status, scheduled_start_at, scheduled_end_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_status_time
    ON delivery.exam_sitting (sitting_status, scheduled_start_at, scheduled_end_at);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_sitting_room_sitting_room
    ON delivery.exam_sitting_room (exam_sitting_id, room_id);

CREATE INDEX IF NOT EXISTS idx_delivery_proctor_assignment_proctor_user
    ON delivery.proctor_assignment (proctor_user_id);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_assignment_student_status
    ON delivery.exam_assignment (student_id, assignment_status);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_assignment_sitting_status
    ON delivery.exam_assignment (exam_sitting_id, assignment_status);

CREATE INDEX IF NOT EXISTS idx_delivery_exam_station_assignment_room_station_status
    ON delivery.exam_station_assignment (exam_sitting_room_id, station_id, status);

