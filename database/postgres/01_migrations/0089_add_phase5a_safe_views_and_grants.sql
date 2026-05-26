-- Phase 5.6 source: docs/phase_5a_individual_grading_runtime_design.md
-- Final hardening and safe views for Phase 5A individual grading runtime.

DROP VIEW IF EXISTS grading.v_grading_job_status;
DROP VIEW IF EXISTS grading.v_grading_run_status;
DROP VIEW IF EXISTS grading.v_question_grading_task_status;
DROP VIEW IF EXISTS grading.v_question_score_summary;
DROP VIEW IF EXISTS grading.v_submission_score_summary;
DROP VIEW IF EXISTS grading.v_manual_review_queue;
DROP VIEW IF EXISTS grading.v_grading_event_summary;

CREATE VIEW grading.v_grading_job_status AS
SELECT
    gj.grading_job_id,
    gj.exam_submission_id,
    gj.submission_seal_id,
    gj.exam_session_id,
    gj.generated_exam_instance_id,
    gj.grading_mode,
    gj.grading_status,
    gj.requested_at,
    gj.started_at,
    gj.finished_at,
    gj.requested_by,
    gj.attempt_count,
    gj.error_code,
    lr.run_no AS last_run_no,
    lr.run_status AS last_run_status,
    COALESCE(task_stats.total_tasks, 0) AS total_tasks,
    COALESCE(task_stats.completed_tasks, 0) AS completed_tasks,
    COALESCE(task_stats.failed_tasks, 0) AS failed_tasks,
    COALESCE(task_stats.needs_review_tasks, 0) AS needs_review_tasks,
    ss.submission_score_id AS current_submission_score_id,
    ss.total_raw_score AS current_total_raw_score,
    ss.total_max_score AS current_total_max_score,
    ss.final_score AS current_final_score,
    ss.score_status AS current_score_status,
    ss.scored_at AS current_scored_at
FROM grading.grading_job gj
LEFT JOIN LATERAL (
    SELECT
        gr.run_no,
        gr.run_status
    FROM grading.grading_run gr
    WHERE gr.grading_job_id = gj.grading_job_id
    ORDER BY gr.run_no DESC
    LIMIT 1
) lr ON true
LEFT JOIN (
    SELECT
        qgt.grading_job_id,
        COUNT(*) AS total_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'COMPLETED') AS completed_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'FAILED') AS failed_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'NEEDS_REVIEW') AS needs_review_tasks
    FROM grading.question_grading_task qgt
    GROUP BY qgt.grading_job_id
) task_stats
    ON task_stats.grading_job_id = gj.grading_job_id
LEFT JOIN grading.submission_score ss
    ON ss.grading_job_id = gj.grading_job_id
   AND ss.is_current = true
   AND ss.score_status <> 'VOIDED';

COMMENT ON VIEW grading.v_grading_job_status IS
    'Safe job-level grading runtime status view without raw evidence payloads or internal stack traces.';

CREATE VIEW grading.v_grading_run_status AS
SELECT
    gr.grading_run_id,
    gr.grading_job_id,
    gr.run_no,
    gr.run_status,
    gr.started_at,
    gr.finished_at,
    gr.worker_id,
    gr.engine_batch_version,
    gr.error_code,
    gj.grading_status AS job_status,
    gj.grading_mode AS job_mode,
    COALESCE(task_stats.total_tasks, 0) AS total_tasks,
    COALESCE(task_stats.completed_tasks, 0) AS completed_tasks,
    COALESCE(task_stats.failed_tasks, 0) AS failed_tasks,
    COALESCE(task_stats.needs_review_tasks, 0) AS needs_review_tasks
FROM grading.grading_run gr
JOIN grading.grading_job gj
    ON gj.grading_job_id = gr.grading_job_id
LEFT JOIN (
    SELECT
        qgt.grading_run_id,
        COUNT(*) AS total_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'COMPLETED') AS completed_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'FAILED') AS failed_tasks,
        COUNT(*) FILTER (WHERE qgt.task_status = 'NEEDS_REVIEW') AS needs_review_tasks
    FROM grading.question_grading_task qgt
    GROUP BY qgt.grading_run_id
) task_stats
    ON task_stats.grading_run_id = gr.grading_run_id;

COMMENT ON VIEW grading.v_grading_run_status IS
    'Safe run-level grading status view with task counters and without raw metadata payloads.';

CREATE VIEW grading.v_question_grading_task_status AS
SELECT
    qgt.question_grading_task_id,
    qgt.grading_run_id,
    qgt.grading_job_id,
    qgt.exam_submission_id,
    qgt.submission_seal_id,
    qgt.generated_exam_question_id,
    qgt.generated_expected_answer_id,
    qgt.question_grading_profile_id,
    qgt.input_source,
    qgt.answer_language,
    qgt.requires_capture,
    qgt.capture_job_id,
    qgt.capture_dataset_id,
    qgt.capture_artifact_id,
    qgt.task_status,
    qgt.max_score,
    qgt.started_at,
    qgt.finished_at,
    qgt.error_code,
    ge.engine_code,
    qgp.comparison_method,
    eac.comparison_status,
    qs.question_score_id,
    qs.raw_score,
    qs.score_status,
    qs.requires_manual_review
FROM grading.question_grading_task qgt
LEFT JOIN grading.grading_engine ge
    ON ge.grading_engine_id = qgt.grading_engine_id
LEFT JOIN assessment.question_grading_profile qgp
    ON qgp.question_grading_profile_id = qgt.question_grading_profile_id
LEFT JOIN grading.expected_actual_comparison eac
    ON eac.question_grading_task_id = qgt.question_grading_task_id
LEFT JOIN grading.question_score qs
    ON qs.question_grading_task_id = qgt.question_grading_task_id;

COMMENT ON VIEW grading.v_question_grading_task_status IS
    'Safe per-task grading runtime status view without raw actual/expected payloads.';

CREATE VIEW grading.v_question_score_summary AS
SELECT
    qs.question_score_id,
    qs.question_grading_task_id,
    qs.exam_submission_id,
    qs.submission_seal_id,
    qs.generated_exam_question_id,
    qs.raw_score,
    qs.max_score,
    qs.score_percent,
    qs.score_status,
    qs.scored_at,
    qs.requires_manual_review,
    ge_scored.engine_code AS scored_engine_code,
    ge_task.engine_code AS task_engine_code,
    qgp.comparison_method,
    qgt.input_source,
    qgt.answer_language
FROM grading.question_score qs
LEFT JOIN grading.grading_engine ge_scored
    ON ge_scored.grading_engine_id = qs.scored_by_engine_id
LEFT JOIN grading.question_grading_task qgt
    ON qgt.question_grading_task_id = qs.question_grading_task_id
LEFT JOIN grading.grading_engine ge_task
    ON ge_task.grading_engine_id = qgt.grading_engine_id
LEFT JOIN assessment.question_grading_profile qgp
    ON qgp.question_grading_profile_id = qgt.question_grading_profile_id;

COMMENT ON VIEW grading.v_question_score_summary IS
    'Safe question-level scoring summary without feedback payloads or raw comparison payloads.';

CREATE VIEW grading.v_submission_score_summary AS
SELECT
    ss.submission_score_id,
    ss.grading_job_id,
    ss.exam_submission_id,
    ss.submission_seal_id,
    ss.score_version_no,
    ss.is_current,
    ss.total_raw_score,
    ss.total_max_score,
    ss.final_score,
    ss.score_status,
    ss.scored_at,
    ss.finalized_at,
    ss.finalized_by,
    gj.grading_mode,
    gj.grading_status
FROM grading.submission_score ss
JOIN grading.grading_job gj
    ON gj.grading_job_id = ss.grading_job_id;

COMMENT ON VIEW grading.v_submission_score_summary IS
    'Safe submission-level score summary with versioning and runtime status fields.';

CREATE VIEW grading.v_manual_review_queue AS
SELECT
    mrq.manual_review_id,
    mrq.exam_submission_id,
    mrq.submission_seal_id,
    mrq.question_grading_task_id,
    mrq.question_score_id,
    mrq.submission_score_id,
    mrq.review_reason,
    mrq.review_status,
    mrq.assigned_to,
    mrq.created_at,
    mrq.resolved_at,
    mrq.resolved_by,
    mrq.note
FROM grading.manual_review_queue mrq;

COMMENT ON VIEW grading.v_manual_review_queue IS
    'Safe manual review queue summary without raw metadata payloads.';

CREATE VIEW grading.v_grading_event_summary AS
SELECT
    gev.grading_event_id,
    gev.grading_job_id,
    gev.grading_run_id,
    gev.question_grading_task_id,
    gev.event_type,
    gev.event_at,
    gev.actor_user_id,
    gev.worker_id,
    gev.created_at,
    gj.grading_status AS job_status,
    gr.run_status,
    qgt.task_status
FROM grading.grading_event gev
LEFT JOIN grading.grading_job gj
    ON gj.grading_job_id = gev.grading_job_id
LEFT JOIN grading.grading_run gr
    ON gr.grading_run_id = gev.grading_run_id
LEFT JOIN grading.question_grading_task qgt
    ON qgt.question_grading_task_id = gev.question_grading_task_id;

COMMENT ON VIEW grading.v_grading_event_summary IS
    'Safe grading event audit summary without exposing event payload JSON.';

GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_job TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_run TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.question_grading_task TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.actual_result TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.expected_actual_comparison TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.question_score TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.submission_score TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.manual_review_queue TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE grading.score_adjustment TO exam_sys_app;
GRANT SELECT, INSERT ON TABLE grading.grading_event TO exam_sys_app;

REVOKE DELETE ON TABLE grading.grading_job FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.grading_run FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.question_grading_task FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.actual_result FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.expected_actual_comparison FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.question_score FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.submission_score FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.manual_review_queue FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.score_adjustment FROM exam_sys_app;
REVOKE DELETE ON TABLE grading.grading_event FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.grading_job FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.grading_run FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.question_grading_task FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.actual_result FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.expected_actual_comparison FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.question_score FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.submission_score FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.manual_review_queue FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.score_adjustment FROM exam_sys_readonly;
REVOKE SELECT ON TABLE grading.grading_event FROM exam_sys_readonly;

GRANT SELECT ON TABLE grading.v_grading_job_status TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_grading_run_status TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_question_grading_task_status TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_question_score_summary TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_submission_score_summary TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_manual_review_queue TO exam_sys_app;
GRANT SELECT ON TABLE grading.v_grading_event_summary TO exam_sys_app;

GRANT SELECT ON TABLE grading.v_grading_job_status TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_grading_run_status TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_question_grading_task_status TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_question_score_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_submission_score_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_manual_review_queue TO exam_sys_readonly;
GRANT SELECT ON TABLE grading.v_grading_event_summary TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.grading_job FROM PUBLIC;
REVOKE ALL ON TABLE grading.grading_run FROM PUBLIC;
REVOKE ALL ON TABLE grading.question_grading_task FROM PUBLIC;
REVOKE ALL ON TABLE grading.actual_result FROM PUBLIC;
REVOKE ALL ON TABLE grading.expected_actual_comparison FROM PUBLIC;
REVOKE ALL ON TABLE grading.question_score FROM PUBLIC;
REVOKE ALL ON TABLE grading.submission_score FROM PUBLIC;
REVOKE ALL ON TABLE grading.manual_review_queue FROM PUBLIC;
REVOKE ALL ON TABLE grading.score_adjustment FROM PUBLIC;
REVOKE ALL ON TABLE grading.grading_event FROM PUBLIC;

REVOKE ALL ON TABLE grading.v_grading_job_status FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_grading_run_status FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_question_grading_task_status FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_question_score_summary FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_submission_score_summary FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_manual_review_queue FROM PUBLIC;
REVOKE ALL ON TABLE grading.v_grading_event_summary FROM PUBLIC;
