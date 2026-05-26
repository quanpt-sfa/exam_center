-- Verifies safe summary view exists for Phase 4.7.4 resource bindings.

DO
$$
BEGIN
    IF to_regclass('delivery.v_exam_session_resource_binding_summary') IS NULL THEN
        RAISE EXCEPTION 'View delivery.v_exam_session_resource_binding_summary does not exist';
    END IF;

    RAISE NOTICE 'PASS: delivery.v_exam_session_resource_binding_summary exists.';
END
$$;
