-- Phase 4.7.6 source: docs/phase_4_7_assessment_modality_grading_profile_foundation.md
-- Final hardening for Phase 4.7 safe views and least-privilege grants.

DROP VIEW IF EXISTS grading.v_grading_engine_registry;

CREATE VIEW grading.v_grading_engine_registry AS
SELECT
    ge.grading_engine_id,
    ge.engine_code,
    ge.engine_name,
    ge.engine_category,
    ge.runtime_kind,
    ge.description,
    ge.is_active,
    ge.created_at,
    ge.updated_at
FROM grading.grading_engine ge;

COMMENT ON VIEW grading.v_grading_engine_registry IS
    'Safe grading engine registry view for operational use without exposing secret-bearing payloads.';

DROP VIEW IF EXISTS capture.v_capture_profile_summary;

CREATE VIEW capture.v_capture_profile_summary AS
SELECT
    cp.capture_profile_id,
    cp.profile_code,
    cp.profile_name,
    cp.source_type,
    cp.source_location_mode,
    cp.default_capture_timing,
    cp.requires_agent,
    cp.status,
    COALESCE(
        array_agg(DISTINCT ge.engine_code) FILTER (WHERE ge.engine_code IS NOT NULL),
        ARRAY[]::varchar[]
    ) AS supported_engine_codes,
    cp.created_at,
    cp.updated_at
FROM capture.capture_profile cp
LEFT JOIN capture.capture_profile_engine_link cpel
    ON cpel.capture_profile_id = cp.capture_profile_id
   AND cpel.is_active = true
LEFT JOIN grading.grading_engine ge
    ON ge.grading_engine_id = cpel.grading_engine_id
GROUP BY
    cp.capture_profile_id,
    cp.profile_code,
    cp.profile_name,
    cp.source_type,
    cp.source_location_mode,
    cp.default_capture_timing,
    cp.requires_agent,
    cp.status,
    cp.created_at,
    cp.updated_at;

COMMENT ON VIEW capture.v_capture_profile_summary IS
    'Safe capture profile summary with linked grading engine codes and without extractor query text.';

DROP VIEW IF EXISTS assessment.v_exam_version_delivery_profile_summary;

CREATE VIEW assessment.v_exam_version_delivery_profile_summary AS
SELECT
    evdp.exam_version_delivery_profile_id,
    evdp.exam_version_id,
    evdp.delivery_mode,
    evdp.work_mode,
    evdp.primary_answer_source,
    evdp.requires_capture,
    evdp.capture_timing,
    cp.profile_code AS default_capture_profile_code,
    ge.engine_code AS default_grading_engine_code,
    evdp.allow_mixed_question_sources,
    evdp.form_autosave_enabled,
    evdp.database_work_mode,
    evdp.status,
    evdp.created_at,
    evdp.updated_at
FROM assessment.exam_version_delivery_profile evdp
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = evdp.default_capture_profile_id
LEFT JOIN grading.grading_engine ge
    ON ge.grading_engine_id = evdp.default_grading_engine_id;

COMMENT ON VIEW assessment.v_exam_version_delivery_profile_summary IS
    'Safe summary of exam version modality and default capture/grading profile codes.';

DROP VIEW IF EXISTS assessment.v_question_grading_profile_summary;

CREATE VIEW assessment.v_question_grading_profile_summary AS
SELECT
    qgp.question_grading_profile_id,
    qgp.question_template_id,
    qgp.exam_version_id,
    qgp.input_source,
    qgp.answer_language,
    qgp.requires_capture,
    qgp.required_capture_type,
    cp.profile_code AS capture_profile_code,
    ge.engine_code AS grading_engine_code,
    qgp.comparison_method,
    qgp.timeout_seconds,
    qgp.max_score,
    qgp.status,
    qgp.created_at,
    qgp.updated_at
FROM assessment.question_grading_profile qgp
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = qgp.capture_profile_id
JOIN grading.grading_engine ge
    ON ge.grading_engine_id = qgp.grading_engine_id;

COMMENT ON VIEW assessment.v_question_grading_profile_summary IS
    'Safe summary of question grading profiles with capture and grading engine codes.';

DROP VIEW IF EXISTS delivery.v_exam_session_resource_binding_summary;

CREATE VIEW delivery.v_exam_session_resource_binding_summary AS
SELECT
    rb.resource_binding_id,
    rb.exam_session_id,
    rb.student_id,
    rb.generated_exam_instance_id,
    rb.capture_profile_id,
    cp.profile_code AS capture_profile_code,
    rb.device_id,
    rb.station_id,
    rb.resource_type,
    rb.resource_location_mode,
    rb.resource_code,
    COALESCE(engine_map.default_engine_code, NULL) AS default_grading_engine_code,
    COALESCE(engine_map.supported_engine_codes, ARRAY[]::varchar[]) AS supported_engine_codes,
    rb.assigned_at,
    rb.activated_at,
    rb.sealed_at,
    rb.released_at,
    rb.status
FROM delivery.exam_session_resource_binding rb
LEFT JOIN capture.capture_profile cp
    ON cp.capture_profile_id = rb.capture_profile_id
LEFT JOIN LATERAL (
    SELECT
        MAX(ge.engine_code) FILTER (WHERE cpel.link_role = 'DEFAULT') AS default_engine_code,
        array_agg(DISTINCT ge.engine_code) FILTER (WHERE ge.engine_code IS NOT NULL) AS supported_engine_codes
    FROM capture.capture_profile_engine_link cpel
    JOIN grading.grading_engine ge
      ON ge.grading_engine_id = cpel.grading_engine_id
    WHERE cpel.capture_profile_id = rb.capture_profile_id
      AND cpel.is_active = true
) AS engine_map ON true;

COMMENT ON VIEW delivery.v_exam_session_resource_binding_summary IS
    'Safe summary of exam session resource bindings without connection refs or raw resource refs.';

GRANT SELECT, INSERT, UPDATE ON TABLE grading.grading_engine TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_profile TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_extractor_query TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE capture.capture_profile_engine_link TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE assessment.exam_version_delivery_profile TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE assessment.question_grading_profile TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE ON TABLE delivery.exam_session_resource_binding TO exam_sys_app;

REVOKE DELETE ON TABLE grading.grading_engine FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_profile FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_extractor_query FROM exam_sys_app;
REVOKE DELETE ON TABLE capture.capture_profile_engine_link FROM exam_sys_app;
REVOKE DELETE ON TABLE assessment.exam_version_delivery_profile FROM exam_sys_app;
REVOKE DELETE ON TABLE assessment.question_grading_profile FROM exam_sys_app;
REVOKE DELETE ON TABLE delivery.exam_session_resource_binding FROM exam_sys_app;

REVOKE SELECT ON TABLE grading.grading_engine FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_extractor_query FROM exam_sys_readonly;
REVOKE SELECT ON TABLE capture.capture_profile_engine_link FROM exam_sys_readonly;
REVOKE SELECT ON TABLE assessment.exam_version_delivery_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE assessment.question_grading_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE delivery.exam_session_resource_binding FROM exam_sys_readonly;

GRANT SELECT ON TABLE grading.v_grading_engine_registry TO exam_sys_app;
GRANT SELECT ON TABLE capture.v_capture_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_exam_version_delivery_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE assessment.v_question_grading_profile_summary TO exam_sys_app;
GRANT SELECT ON TABLE delivery.v_exam_session_resource_binding_summary TO exam_sys_app;

GRANT SELECT ON TABLE grading.v_grading_engine_registry TO exam_sys_readonly;
GRANT SELECT ON TABLE capture.v_capture_profile_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_exam_version_delivery_profile_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE assessment.v_question_grading_profile_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE delivery.v_exam_session_resource_binding_summary TO exam_sys_readonly;

REVOKE ALL ON TABLE grading.grading_engine FROM PUBLIC;
REVOKE ALL ON TABLE capture.capture_profile FROM PUBLIC;
REVOKE ALL ON TABLE capture.capture_extractor_query FROM PUBLIC;
REVOKE ALL ON TABLE capture.capture_profile_engine_link FROM PUBLIC;
REVOKE ALL ON TABLE assessment.exam_version_delivery_profile FROM PUBLIC;
REVOKE ALL ON TABLE assessment.question_grading_profile FROM PUBLIC;
REVOKE ALL ON TABLE delivery.exam_session_resource_binding FROM PUBLIC;

REVOKE ALL ON TABLE grading.v_grading_engine_registry FROM PUBLIC;
REVOKE ALL ON TABLE capture.v_capture_profile_summary FROM PUBLIC;
REVOKE ALL ON TABLE assessment.v_exam_version_delivery_profile_summary FROM PUBLIC;
REVOKE ALL ON TABLE assessment.v_question_grading_profile_summary FROM PUBLIC;
REVOKE ALL ON TABLE delivery.v_exam_session_resource_binding_summary FROM PUBLIC;