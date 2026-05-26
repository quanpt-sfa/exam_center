-- Verifies v_phase3_session_delivery_state keeps safe projection and required runtime fields.

DO
$$
DECLARE
    issues text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state' AND column_name = 'exam_session_id'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state' AND column_name = 'session_status'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state' AND column_name = 'generated_question_count'
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'missing required runtime columns';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'delivery' AND table_name = 'v_phase3_session_delivery_state'
          AND column_name IN (
              'client_fingerprint',
              'metadata_json',
              'event_payload_json',
              'parameter_value_json',
              'expected_payload',
              'photo_ref'
          )
    ) THEN
        issues := issues || CASE WHEN issues = '' THEN '' ELSE '; ' END
            || 'view exposes sensitive columns';
    END IF;

    IF issues <> '' THEN
        RAISE EXCEPTION 'Phase 3.3 session delivery view contract failed: %', issues;
    END IF;

    RAISE NOTICE 'PASS: v_phase3_session_delivery_state contract is valid and safe.';
END
$$;
