-- Phase 4.6 source: docs/phase_4_submission_autosave_seal_capture_pipeline.md
-- Finalizes Phase 4 hardening, safe views, and operational access rules.

-- Remove DELETE on Phase 4 evidence/runtime tables for app role.
REVOKE DELETE ON TABLE submission.exam_submission FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.answer_state FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.answer_save_batch FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.answer_save_item FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.submission_seal FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.sealed_answer FROM exam_sys_app;
REVOKE DELETE ON TABLE submission.answer_conflict FROM exam_sys_app;

REVOKE DELETE ON TABLE capture.capture_job FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_artifact FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_dataset FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_dataset_row FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_job_event FROM exam_sys_app;

-- Ensure readonly role has no direct SELECT on sensitive Phase 4 tables.
REVOKE SELECT ON TABLE submission.answer_state FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.answer_save_batch FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.answer_save_item FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.submission_seal FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.sealed_answer FROM exam_sys_readonly;
REVOKE SELECT ON TABLE submission.answer_conflict FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_artifact FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_dataset_row FROM exam_sys_readonly;

CREATE OR REPLACE VIEW submission.v_student_answer_resume_state AS
SELECT
    es.exam_submission_id,
    es.exam_session_id,
    es.generated_exam_instance_id,
    es.submission_status,
    geq.generated_exam_question_id,
    geq.question_order,
    geq.question_type,
    ast.answer_type,
    ast.answer_text,
    ast.answer_payload_json,
    ast.answer_hash,
    ast.client_version,
    ast.server_version,
    ast.last_saved_at,
    ast.answer_status
FROM submission.exam_submission es
JOIN delivery.generated_exam_question geq
    ON geq.generated_exam_instance_id = es.generated_exam_instance_id
LEFT JOIN submission.answer_state ast
    ON ast.exam_submission_id = es.exam_submission_id
   AND ast.generated_exam_question_id = geq.generated_exam_question_id
WHERE NOT EXISTS (
    SELECT 1
    FROM submission.submission_seal ss
    WHERE ss.exam_submission_id = es.exam_submission_id
      AND ss.seal_status IN ('SEALED', 'SUPERSEDED', 'VOIDED')
);

COMMENT ON VIEW submission.v_student_answer_resume_state IS
    'Student workspace resume state view. Excludes submissions that already reached sealed statuses.';

CREATE OR REPLACE VIEW submission.v_submission_status AS
SELECT
    es.exam_submission_id,
    es.exam_session_id,
    es.generated_exam_instance_id,
    es.submission_status,
    es.opened_at,
    es.first_saved_at,
    es.last_saved_at,
    es.submitted_at,
    es.sealed_at,
    es.seal_reason,
    COALESCE(ast.answer_state_count, 0) AS answer_state_count,
    COALESCE(sa.sealed_answer_count, 0) AS sealed_answer_count
FROM submission.exam_submission es
LEFT JOIN (
    SELECT
        exam_submission_id,
        COUNT(*) AS answer_state_count
    FROM submission.answer_state
    GROUP BY exam_submission_id
) ast
    ON ast.exam_submission_id = es.exam_submission_id
LEFT JOIN (
    SELECT
        exam_submission_id,
        COUNT(*) AS sealed_answer_count
    FROM submission.sealed_answer
    GROUP BY exam_submission_id
) sa
    ON sa.exam_submission_id = es.exam_submission_id;

COMMENT ON VIEW submission.v_submission_status IS
    'Operational submission status summary with answer-state and sealed-answer counts.';

CREATE OR REPLACE VIEW submission.v_sealed_submission_summary AS
SELECT
    ss.exam_submission_id,
    ss.submission_seal_id,
    ss.seal_status,
    ss.seal_reason,
    ss.sealed_at,
    ss.answer_count,
    ss.submission_hash
FROM submission.submission_seal ss;

COMMENT ON VIEW submission.v_sealed_submission_summary IS
    'Safe sealed-submission summary without exposing raw answer payloads.';

CREATE OR REPLACE VIEW capture.v_capture_job_status AS
SELECT
    cj.capture_job_id,
    cj.exam_submission_id,
    cj.submission_seal_id,
    cj.capture_type,
    cj.capture_status,
    cj.requested_at,
    cj.started_at,
    cj.finished_at,
    cj.attempt_count,
    COALESCE(ca.artifact_count, 0) AS artifact_count,
    COALESCE(cd.dataset_count, 0) AS dataset_count,
    cj.error_code
FROM capture.capture_job cj
LEFT JOIN (
    SELECT
        capture_job_id,
        COUNT(*) AS artifact_count
    FROM capture.capture_artifact
    GROUP BY capture_job_id
) ca
    ON ca.capture_job_id = cj.capture_job_id
LEFT JOIN (
    SELECT
        capture_job_id,
        COUNT(*) AS dataset_count
    FROM capture.capture_dataset
    GROUP BY capture_job_id
) cd
    ON cd.capture_job_id = cj.capture_job_id;

COMMENT ON VIEW capture.v_capture_job_status IS
    'Operational capture monitoring view without raw artifact payloads or verbose internal errors.';

GRANT SELECT ON TABLE submission.v_student_answer_resume_state TO exam_sys_app;
GRANT SELECT ON TABLE submission.v_submission_status TO exam_sys_app;
GRANT SELECT ON TABLE submission.v_sealed_submission_summary TO exam_sys_app;
GRANT SELECT ON TABLE capture.v_capture_job_status TO exam_sys_app;

GRANT SELECT ON TABLE submission.v_student_answer_resume_state TO exam_sys_readonly;
GRANT SELECT ON TABLE submission.v_submission_status TO exam_sys_readonly;
GRANT SELECT ON TABLE submission.v_sealed_submission_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE capture.v_capture_job_status TO exam_sys_readonly;
