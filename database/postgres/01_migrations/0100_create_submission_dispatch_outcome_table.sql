-- S2W-3.2 source: durable dispatcher outcome persistence.
-- Creates append-only submission dispatch outcome audit table and latest-state view.

CREATE TABLE IF NOT EXISTS submission.submission_dispatch_outcome (
    submission_dispatch_outcome_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_submission_id bigint NOT NULL,
    submission_seal_id bigint NULL,
    exam_version_id bigint NULL,
    dispatch_route varchar(40) NOT NULL,
    dispatch_status varchar(40) NOT NULL,
    dispatch_identity_key varchar(255) NOT NULL,
    client_idempotency_key varchar(255) NULL,
    capture_job_id bigint NULL,
    grading_job_id bigint NULL,
    blockers_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    readiness_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    dispatch_context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    message text NULL,
    requested_by bigint NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_sub_dispatch_outcome_route CHECK (
        dispatch_route IN (
            'DIRECT_GRADING',
            'CAPTURE_THEN_GRADING',
            'MANUAL_REVIEW_REQUIRED',
            'NOT_READY'
        )
    ),
    CONSTRAINT ck_sub_dispatch_outcome_status CHECK (
        dispatch_status IN (
            'DISPATCHED',
            'ALREADY_DISPATCHED',
            'NOT_READY',
            'MANUAL_REVIEW_REQUIRED',
            'FAILED'
        )
    ),
    CONSTRAINT ck_sub_dispatch_outcome_identity_key CHECK (length(trim(dispatch_identity_key)) > 0),
    CONSTRAINT ck_sub_dispatch_outcome_blockers_json_array CHECK (jsonb_typeof(blockers_json) = 'array'),
    CONSTRAINT ck_sub_dispatch_outcome_readiness_json_object CHECK (jsonb_typeof(readiness_snapshot_json) = 'object'),
    CONSTRAINT ck_sub_dispatch_outcome_dispatch_context_json_object CHECK (jsonb_typeof(dispatch_context_json) = 'object'),
    CONSTRAINT ck_sub_dispatch_outcome_metadata_json_object CHECK (jsonb_typeof(metadata_json) = 'object'),
    CONSTRAINT fk_sub_dispatch_outcome_submission FOREIGN KEY (exam_submission_id)
        REFERENCES submission.exam_submission(exam_submission_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_sub_dispatch_outcome_seal FOREIGN KEY (submission_seal_id)
        REFERENCES submission.submission_seal(submission_seal_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_sub_dispatch_outcome_capture_job FOREIGN KEY (capture_job_id)
        REFERENCES capture.capture_job(capture_job_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_sub_dispatch_outcome_grading_job FOREIGN KEY (grading_job_id)
        REFERENCES grading.grading_job(grading_job_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_sub_dispatch_outcome_requested_by FOREIGN KEY (requested_by)
        REFERENCES identity.app_user(user_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sub_dispatch_outcome_submission_id
    ON submission.submission_dispatch_outcome (exam_submission_id);

CREATE INDEX IF NOT EXISTS idx_sub_dispatch_outcome_submission_seal_id
    ON submission.submission_dispatch_outcome (submission_seal_id);

CREATE INDEX IF NOT EXISTS idx_sub_dispatch_outcome_status
    ON submission.submission_dispatch_outcome (dispatch_status);

CREATE INDEX IF NOT EXISTS idx_sub_dispatch_outcome_route
    ON submission.submission_dispatch_outcome (dispatch_route);

CREATE INDEX IF NOT EXISTS idx_sub_dispatch_outcome_created_at
    ON submission.submission_dispatch_outcome (created_at);

CREATE OR REPLACE VIEW submission.v_submission_dispatch_latest AS
SELECT
    ranked.submission_dispatch_outcome_id,
    ranked.exam_submission_id,
    ranked.submission_seal_id,
    ranked.exam_version_id,
    ranked.dispatch_route,
    ranked.dispatch_status,
    ranked.dispatch_identity_key,
    ranked.client_idempotency_key,
    ranked.capture_job_id,
    ranked.grading_job_id,
    ranked.blockers_json,
    ranked.readiness_snapshot_json,
    ranked.dispatch_context_json,
    ranked.metadata_json,
    ranked.message,
    ranked.requested_by,
    ranked.requested_at,
    ranked.created_at
FROM (
    SELECT
        sdo.*,
        row_number() OVER (
            PARTITION BY sdo.exam_submission_id
            ORDER BY sdo.created_at DESC, sdo.submission_dispatch_outcome_id DESC
        ) AS rn
    FROM submission.submission_dispatch_outcome sdo
) ranked
WHERE ranked.rn = 1;

GRANT SELECT, INSERT ON TABLE submission.submission_dispatch_outcome TO exam_sys_app;
REVOKE UPDATE ON TABLE submission.submission_dispatch_outcome FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.submission_dispatch_outcome FROM exam_sys_app;

REVOKE SELECT ON TABLE submission.submission_dispatch_outcome FROM exam_sys_readonly;
GRANT SELECT ON TABLE submission.v_submission_dispatch_latest TO exam_sys_readonly;
GRANT SELECT ON TABLE submission.v_submission_dispatch_latest TO exam_sys_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA submission TO exam_sys_readonly;

REVOKE ALL ON TABLE submission.submission_dispatch_outcome FROM PUBLIC;
REVOKE ALL ON TABLE submission.v_submission_dispatch_latest FROM PUBLIC;
