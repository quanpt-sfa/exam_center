-- Migration: Create system settings and settings history tables in ops schema
-- Handles runtime configuration parameters, brand metadata, and audit logs.

CREATE TABLE IF NOT EXISTS ops.system_settings (
    settings_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    academy_name varchar(255) NOT NULL,
    portal_logo_url text NULL,
    exam_regulations text NOT NULL,
    support_email varchar(255) NOT NULL,
    support_hotline varchar(50) NOT NULL,
    session_heartbeat_seconds integer NOT NULL DEFAULT 30,
    concurrent_login_check boolean NOT NULL DEFAULT true,
    autosave_interval_seconds integer NOT NULL DEFAULT 10,
    exam_start_window_minutes integer NOT NULL DEFAULT 15,
    late_entry_window_minutes integer NOT NULL DEFAULT 10,
    min_proctors_per_room integer NOT NULL DEFAULT 1,
    max_sessions_per_proctor_per_day integer NOT NULL DEFAULT 3,
    version integer NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by bigint NULL,
    CONSTRAINT ck_ops_system_settings_heartbeat CHECK (session_heartbeat_seconds >= 5 AND session_heartbeat_seconds <= 300),
    CONSTRAINT ck_ops_system_settings_autosave CHECK (autosave_interval_seconds >= 5 AND autosave_interval_seconds <= 120),
    CONSTRAINT ck_ops_system_settings_start_window CHECK (exam_start_window_minutes >= 0 AND exam_start_window_minutes <= 120),
    CONSTRAINT ck_ops_system_settings_late_entry CHECK (late_entry_window_minutes >= 0 AND late_entry_window_minutes <= 120),
    CONSTRAINT ck_ops_system_settings_min_proctors CHECK (min_proctors_per_room >= 1),
    CONSTRAINT ck_ops_system_settings_max_sessions CHECK (max_sessions_per_proctor_per_day >= 1),
    CONSTRAINT fk_ops_system_settings_updated_by FOREIGN KEY (updated_by)
        REFERENCES identity.app_user(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ops.system_settings_history (
    history_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    settings_id bigint NOT NULL,
    academy_name varchar(255) NOT NULL,
    portal_logo_url text NULL,
    exam_regulations text NOT NULL,
    support_email varchar(255) NOT NULL,
    support_hotline varchar(50) NOT NULL,
    session_heartbeat_seconds integer NOT NULL,
    concurrent_login_check boolean NOT NULL,
    autosave_interval_seconds integer NOT NULL,
    exam_start_window_minutes integer NOT NULL,
    late_entry_window_minutes integer NOT NULL,
    min_proctors_per_room integer NOT NULL,
    max_sessions_per_proctor_per_day integer NOT NULL,
    version integer NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    changed_by bigint NULL,
    change_reason text NULL,
    CONSTRAINT fk_ops_system_settings_hist_updated_by FOREIGN KEY (changed_by)
        REFERENCES identity.app_user(user_id) ON DELETE SET NULL
);

-- Seed initial settings row
INSERT INTO ops.system_settings (
    academy_name,
    portal_logo_url,
    exam_regulations,
    support_email,
    support_hotline,
    session_heartbeat_seconds,
    concurrent_login_check,
    autosave_interval_seconds,
    exam_start_window_minutes,
    late_entry_window_minutes,
    min_proctors_per_room,
    max_sessions_per_proctor_per_day,
    version,
    updated_at,
    updated_by
) VALUES (
    'Học viện Công nghệ Bưu chính Viễn thông',
    NULL,
    '1. Thí sinh phải mặt đúng giờ quy định.
2. Không mang thiết bị ghi âm, ghi hình hoặc tài liệu không được cho phép vào phòng thi.
3. Tuyệt đối không được gian lận hoặc trao đổi bài thi.',
    'support@ptit.edu.vn',
    '0243354113',
    30,
    true,
    10,
    15,
    10,
    1,
    3,
    1,
    now(),
    NULL
) ON CONFLICT DO NOTHING;

-- Trigger to record update history
CREATE OR REPLACE FUNCTION ops.trg_record_system_settings_history()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO ops.system_settings_history (
        settings_id,
        academy_name,
        portal_logo_url,
        exam_regulations,
        support_email,
        support_hotline,
        session_heartbeat_seconds,
        concurrent_login_check,
        autosave_interval_seconds,
        exam_start_window_minutes,
        late_entry_window_minutes,
        min_proctors_per_room,
        max_sessions_per_proctor_per_day,
        version,
        changed_at,
        changed_by
    ) VALUES (
        NEW.settings_id,
        NEW.academy_name,
        NEW.portal_logo_url,
        NEW.exam_regulations,
        NEW.support_email,
        NEW.support_hotline,
        NEW.session_heartbeat_seconds,
        NEW.concurrent_login_check,
        NEW.autosave_interval_seconds,
        NEW.exam_start_window_minutes,
        NEW.late_entry_window_minutes,
        NEW.min_proctors_per_room,
        NEW.max_sessions_per_proctor_per_day,
        NEW.version,
        now(),
        NEW.updated_by
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_system_settings_after_update
    AFTER UPDATE ON ops.system_settings
    FOR EACH ROW
    EXECUTE FUNCTION ops.trg_record_system_settings_history();

-- Grant permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_app') THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE ops.system_settings TO exam_sys_app;
        GRANT SELECT, INSERT ON TABLE ops.system_settings_history TO exam_sys_app;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        GRANT SELECT ON TABLE ops.system_settings TO exam_sys_readonly;
        GRANT SELECT ON TABLE ops.system_settings_history TO exam_sys_readonly;
    END IF;
END
$$;
