-- Verifies Phase 3.1 safe views exist with required columns.

DO
$$
DECLARE
    missing_views text := '';
    issues text := '';
BEGIN
    IF to_regclass('delivery.v_student_exam_launch_state') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_student_exam_launch_state';
    END IF;

    IF to_regclass('delivery.v_proctor_active_session_monitor') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_proctor_active_session_monitor';
    END IF;

    IF to_regclass('delivery.v_exam_session_timeline') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_exam_session_timeline';
    END IF;

    IF missing_views <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.1 safe views: %', missing_views;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_student_exam_launch_state' AND column_name = 'binding_status'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_student_exam_launch_state' AND column_name = 'asset_tag'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_student_exam_launch_state missing binding_status/asset_tag';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_proctor_active_session_monitor' AND column_name = 'photo_ref'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_proctor_active_session_monitor' AND column_name = 'last_activity_at'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_proctor_active_session_monitor missing photo_ref/last_activity_at';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_exam_session_timeline' AND column_name = 'event_type'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_exam_session_timeline' AND column_name = 'event_at'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_exam_session_timeline missing event_type/event_at';
    END IF;

    IF issues <> '' THEN
        RAISE EXCEPTION 'Phase 3.1 safe view column validation failed: %', issues;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1 safe views exist with required columns.';
END
$$;
