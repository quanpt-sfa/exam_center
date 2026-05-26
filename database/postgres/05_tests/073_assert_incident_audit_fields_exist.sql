-- Verifies additive incident audit columns, table, and indexes.

DO
$$
DECLARE
    missing_columns text := '';
    missing_indexes text := '';
    legacy_indexes text := '';
BEGIN
    FOREACH missing_columns IN ARRAY ARRAY[]::text[] LOOP
        NULL;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_session_incident'
          AND column_name = 'updated_by'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE ', ' END || 'delivery.exam_session_incident.updated_by';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_session_incident'
          AND column_name = 'updated_at'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE ', ' END || 'delivery.exam_session_incident.updated_at';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_session_incident'
          AND column_name = 'resolution_note'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE ', ' END || 'delivery.exam_session_incident.resolution_note';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'delivery'
          AND table_name = 'exam_session_incident_history'
    ) THEN
        missing_columns := missing_columns || CASE WHEN missing_columns = '' THEN '' ELSE ', ' END || 'delivery.exam_session_incident_history';
    END IF;

    IF missing_columns <> '' THEN
        RAISE EXCEPTION 'Missing incident audit schema artifacts: %', missing_columns;
    END IF;

    FOREACH missing_indexes IN ARRAY ARRAY[]::text[] LOOP
        NULL;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'delivery'
                    AND tablename = 'exam_session_incident_history'
                    AND indexname = 'idx_inc_hist_incident_changed'
                    AND indexdef ILIKE '%(incident_id, changed_at DESC, incident_history_id DESC)%'
    ) THEN
                missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_inc_hist_incident_changed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'delivery'
                    AND tablename = 'exam_session_incident_history'
                    AND indexname = 'idx_inc_hist_actor_changed'
                    AND indexdef ILIKE '%(actor_user_id, changed_at DESC, incident_history_id DESC)%'
                    AND indexdef ILIKE '%WHERE (actor_user_id IS NOT NULL)%'
    ) THEN
                missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_inc_hist_actor_changed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'delivery'
                    AND tablename = 'exam_session_incident_history'
                    AND indexname = 'idx_inc_hist_status_changed'
                    AND indexdef ILIKE '%(to_status, changed_at DESC, incident_history_id DESC)%'
                    AND indexdef ILIKE '%WHERE (to_status IS NOT NULL)%'
    ) THEN
                missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || 'idx_inc_hist_status_changed';
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing incident audit indexes: %', missing_indexes;
    END IF;

        SELECT string_agg(indexname, ', ' ORDER BY indexname)
        INTO legacy_indexes
        FROM pg_indexes
        WHERE schemaname = 'delivery'
            AND tablename = 'exam_session_incident_history'
            AND indexname IN (
                    'idx_delivery_exam_session_incident_history_incident_changed_at_desc',
                    'idx_delivery_exam_session_incident_history_actor_user_changed_at_desc',
                    'idx_delivery_exam_session_incident_history_to_status_changed_at_desc',
                    'idx_delivery_exam_session_incident_history_incident_changed_at_',
                    'idx_delivery_exam_session_incident_history_actor_user_changed_a',
                    'idx_delivery_exam_session_incident_history_to_status_changed_at'
            );

        IF legacy_indexes IS NOT NULL THEN
                RAISE EXCEPTION 'Legacy/truncated incident audit indexes still exist: %', legacy_indexes;
        END IF;

    RAISE NOTICE 'PASS: Incident audit columns, table, and indexes exist.';
END
$$;