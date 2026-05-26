-- MD-8: Add worker claim/retry lifecycle columns and statuses for importing.import_job.

ALTER TABLE importing.import_job
    ADD COLUMN IF NOT EXISTS claimed_by varchar(255) NULL,
    ADD COLUMN IF NOT EXISTS claimed_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS attempt_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS next_run_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS last_error_code varchar(100) NULL,
    ADD COLUMN IF NOT EXISTS last_error_message text NULL;

UPDATE importing.import_job
SET
    updated_at = coalesce(updated_at, created_at, now()),
    attempt_count = coalesce(attempt_count, 0),
    max_attempts = CASE WHEN coalesce(max_attempts, 0) <= 0 THEN 3 ELSE max_attempts END;

ALTER TABLE importing.import_job
    ALTER COLUMN updated_at SET DEFAULT now();

DO
$$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_importing_import_job_status'
          AND conrelid = 'importing.import_job'::regclass
    ) THEN
        ALTER TABLE importing.import_job
            DROP CONSTRAINT ck_importing_import_job_status;
    END IF;
END
$$;

ALTER TABLE importing.import_job
    ADD CONSTRAINT ck_importing_import_job_status CHECK (
        job_status IN (
            'CREATED',
            'UPLOADED',
            'PARSED',
            'VALIDATED',
            'COMMITTED',
            'ROLLED_BACK',
            'FAILED',
            'QUEUED',
            'CLAIMED',
            'RUNNING',
            'SUCCEEDED',
            'RETRYING',
            'DEAD_LETTERED',
            'CANCELLED'
        )
    );

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_importing_import_job_max_attempts_positive'
          AND conrelid = 'importing.import_job'::regclass
    ) THEN
        ALTER TABLE importing.import_job
            ADD CONSTRAINT ck_importing_import_job_max_attempts_positive CHECK (max_attempts > 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_importing_import_job_worker_claim
    ON importing.import_job (job_status, next_run_at, lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_importing_import_job_claimed_by
    ON importing.import_job (claimed_by);
