-- Verifies Phase 3.3 final runtime and integrity views exist with required columns.

DO
$$
DECLARE
    missing_views text := '';
    issues text := '';
BEGIN
    IF to_regclass('delivery.v_phase3_session_delivery_state') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_phase3_session_delivery_state';
    END IF;

    IF to_regclass('delivery.v_phase3_integrity_summary') IS NULL THEN
        missing_views := missing_views || CASE WHEN missing_views = '' THEN '' ELSE ', ' END || 'delivery.v_phase3_integrity_summary';
    END IF;

    IF missing_views <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.3 views: %', missing_views;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state' AND column_name = 'generated_question_count'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state' AND column_name = 'asset_tag'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_phase3_session_delivery_state missing generated_question_count/asset_tag';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_integrity_summary' AND column_name = 'generated_instances'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_integrity_summary' AND column_name = 'generated_questions'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'v_phase3_integrity_summary missing generated_instances/generated_questions';
    END IF;

    IF issues <> '' THEN
        RAISE EXCEPTION 'Phase 3.3 view validation failed: %', issues;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.3 final views exist with required columns.';
END
$$;
