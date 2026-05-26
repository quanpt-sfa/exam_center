DO
$$
DECLARE
    legacy_index_name text;
BEGIN
    FOR legacy_index_name IN
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'delivery'
          AND tablename = 'exam_session_incident_history'
          AND indexname IN (
              'idx_delivery_exam_session_incident_history_incident_changed_at_',
              'idx_delivery_exam_session_incident_history_actor_user_changed_a',
              'idx_delivery_exam_session_incident_history_to_status_changed_at'
          )
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS delivery.%I', legacy_index_name);
    END LOOP;
END
$$;

CREATE INDEX IF NOT EXISTS idx_inc_hist_incident_changed
    ON delivery.exam_session_incident_history (incident_id, changed_at DESC, incident_history_id DESC);

CREATE INDEX IF NOT EXISTS idx_inc_hist_actor_changed
    ON delivery.exam_session_incident_history (actor_user_id, changed_at DESC, incident_history_id DESC)
    WHERE actor_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_inc_hist_status_changed
    ON delivery.exam_session_incident_history (to_status, changed_at DESC, incident_history_id DESC)
    WHERE to_status IS NOT NULL;