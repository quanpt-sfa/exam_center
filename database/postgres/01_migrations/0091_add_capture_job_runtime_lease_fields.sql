-- S2W-5.2: Persist runtime lease ownership/heartbeat fields for capture job claim/resume.

ALTER TABLE IF EXISTS capture.capture_job
    ADD COLUMN IF NOT EXISTS lease_owner_worker_id varchar(150) NULL,
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS last_heartbeat_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_status_lease_expires_at
    ON capture.capture_job (capture_status, lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_capture_capture_job_lease_owner_worker_id
    ON capture.capture_job (lease_owner_worker_id);

-- Keep app-role runtime permissions aligned with existing capture table policy.
GRANT SELECT, UPDATE ON TABLE capture.capture_job TO exam_sys_app;

-- Ensure no DELETE grant is introduced by this migration.
REVOKE DELETE ON TABLE capture.capture_job FROM exam_sys_app;

-- Preserve readonly restriction on sensitive capture base table.
REVOKE SELECT ON TABLE capture.capture_job FROM exam_sys_readonly;
