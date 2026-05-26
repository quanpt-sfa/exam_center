-- Verifies primary key exists on delivery.exam_session_resource_binding.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'delivery.exam_session_resource_binding'::regclass
          AND c.contype = 'p'
    ) THEN
        RAISE EXCEPTION 'Primary key missing on delivery.exam_session_resource_binding';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_resource_binding primary key exists.';
END
$$;
