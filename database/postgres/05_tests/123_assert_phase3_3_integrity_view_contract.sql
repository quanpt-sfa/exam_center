-- Verifies v_phase3_integrity_summary projection and metric column typing.

DO
$$
DECLARE
    missing_cols integer;
    bad_type_cols integer;
BEGIN
    SELECT COUNT(*)
    INTO missing_cols
    FROM (
        SELECT 'exam_sitting_id' AS col
        UNION ALL SELECT 'assigned_students'
        UNION ALL SELECT 'station_assignments'
        UNION ALL SELECT 'sessions_created'
        UNION ALL SELECT 'active_sessions'
        UNION ALL SELECT 'generated_instances'
        UNION ALL SELECT 'generated_questions'
        UNION ALL SELECT 'incidents'
        UNION ALL SELECT 'transfers'
        UNION ALL SELECT 'reschedules'
    ) e
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'delivery'
          AND c.table_name = 'v_phase3_integrity_summary'
          AND c.column_name = e.col
    );

    IF missing_cols <> 0 THEN
        RAISE EXCEPTION 'v_phase3_integrity_summary is missing required metric columns';
    END IF;

    SELECT COUNT(*)
    INTO bad_type_cols
    FROM information_schema.columns c
    WHERE c.table_schema = 'delivery'
      AND c.table_name = 'v_phase3_integrity_summary'
      AND c.column_name IN (
          'assigned_students',
          'station_assignments',
          'sessions_created',
          'active_sessions',
          'generated_instances',
          'generated_questions',
          'incidents',
          'transfers',
          'reschedules'
      )
      AND c.data_type NOT IN ('smallint', 'integer', 'bigint', 'numeric', 'real', 'double precision');

    IF bad_type_cols <> 0 THEN
        RAISE EXCEPTION 'v_phase3_integrity_summary has non-numeric metric columns';
    END IF;

    RAISE NOTICE 'PASS: v_phase3_integrity_summary contract and metric types are valid.';
END
$$;
