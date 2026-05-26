-- S2W-4H-C: Persist runtime lease ownership/heartbeat fields for RUNNING grading jobs.

ALTER TABLE IF EXISTS grading.grading_job
    ADD COLUMN IF NOT EXISTS lease_owner_worker_id varchar(150) NULL,
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS last_heartbeat_at timestamptz NULL;

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'grading_job'
          AND c.conname = 'ck_grading_grading_job_lease_owner_expires_consistency'
    ) THEN
        ALTER TABLE grading.grading_job
            ADD CONSTRAINT ck_grading_grading_job_lease_owner_expires_consistency CHECK (
                (lease_owner_worker_id IS NULL AND lease_expires_at IS NULL)
                OR (lease_owner_worker_id IS NOT NULL)
            );
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_lease_expires_at
    ON grading.grading_job (lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_lease_owner_worker_id
    ON grading.grading_job (lease_owner_worker_id);

CREATE INDEX IF NOT EXISTS idx_grading_grading_job_running_lease_expires
    ON grading.grading_job (lease_expires_at)
    WHERE grading_status = 'RUNNING';
