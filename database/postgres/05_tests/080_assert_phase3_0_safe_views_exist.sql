-- Verifies Phase 3.0 safe views exist with required columns.

DO
$$
DECLARE
    view_name text;
    missing_views text := '';
    missing_columns text := '';
BEGIN
    FOREACH view_name IN ARRAY ARRAY[
        'delivery.v_exam_sitting_room_summary',
        'delivery.v_room_station_readiness',
        'delivery.v_proctor_room_roster'
    ]
    LOOP
        IF to_regclass(view_name) IS NULL THEN
            missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || view_name;
        END IF;
    END LOOP;

    IF missing_views <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0 safe views: %', missing_views;
    END IF;

    -- Required columns for v_exam_sitting_room_summary
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_exam_sitting_room_summary'
          AND column_name = 'assigned_student_count'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_exam_sitting_room_summary'
          AND column_name = 'assigned_station_count'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE '; ' END
            || 'delivery.v_exam_sitting_room_summary missing assignment count columns';
    END IF;

    -- Required columns for v_room_station_readiness
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_room_station_readiness'
          AND column_name = 'last_checkin_at'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_room_station_readiness'
          AND column_name = 'last_health_status'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE '; ' END
            || 'delivery.v_room_station_readiness missing last checkin/health columns';
    END IF;

    -- Required columns for v_proctor_room_roster
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_proctor_room_roster'
          AND column_name = 'photo_ref'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'v_proctor_room_roster'
          AND column_name = 'student_code'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE '; ' END
            || 'delivery.v_proctor_room_roster missing photo_ref/student_code columns';
    END IF;

    IF missing_columns <> '' THEN
        RAISE EXCEPTION 'Phase 3.0 safe view column validation failed: %', missing_columns;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0 safe views exist with required columns.';
END
$$;
