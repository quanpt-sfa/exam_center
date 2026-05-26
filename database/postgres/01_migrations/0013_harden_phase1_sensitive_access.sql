-- Phase 1.1 hardening
-- Restrict readonly role from direct sensitive tables and expose safe views.

REVOKE SELECT ON TABLE academic.student_accessibility_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE academic.student_socioeconomic_profile FROM exam_sys_readonly;
REVOKE SELECT ON TABLE academic.student_consent FROM exam_sys_readonly;
REVOKE SELECT ON TABLE identity.contact_point FROM exam_sys_readonly;
REVOKE SELECT ON TABLE identity.address FROM exam_sys_readonly;

CREATE OR REPLACE VIEW academic.v_student_accessibility_exam_accommodation AS
SELECT
    student_id,
    exam_accommodation_flag,
    extra_time_percent,
    valid_from,
    valid_to
FROM academic.student_accessibility_profile;

COMMENT ON VIEW academic.v_student_accessibility_exam_accommodation IS
    'Safe readonly view for exam accommodation operations without restricted notes.';

CREATE OR REPLACE VIEW academic.v_student_learning_context_summary AS
SELECT
    student_id,
    primary_device_access,
    internet_access_level,
    preferred_learning_mode,
    sql_experience_level,
    valid_from,
    valid_to
FROM academic.student_learning_context;

COMMENT ON VIEW academic.v_student_learning_context_summary IS
    'Safe readonly summary view for student learning context.';

CREATE OR REPLACE VIEW identity.v_person_primary_contact AS
SELECT
    person_id,
    contact_type,
    contact_value,
    is_verified,
    valid_from,
    valid_to
FROM identity.contact_point
WHERE is_primary = true;

COMMENT ON VIEW identity.v_person_primary_contact IS
    'Safe readonly view exposing only primary contact points.';

CREATE OR REPLACE VIEW identity.v_person_primary_address AS
SELECT
    person_id,
    address_type,
    address_line,
    ward,
    district,
    province,
    country,
    valid_from,
    valid_to
FROM identity.address
WHERE is_primary = true;

COMMENT ON VIEW identity.v_person_primary_address IS
    'Safe readonly view exposing only primary addresses.';

CREATE OR REPLACE VIEW academic.v_student_consent_status AS
SELECT
    student_id,
    consent_type,
    purpose_code,
    consent_status,
    given_at,
    withdrawn_at,
    version_no
FROM academic.student_consent;

COMMENT ON VIEW academic.v_student_consent_status IS
    'Safe readonly consent status view excluding evidence references.';

GRANT SELECT ON TABLE academic.v_student_accessibility_exam_accommodation TO exam_sys_readonly;
GRANT SELECT ON TABLE academic.v_student_learning_context_summary TO exam_sys_readonly;
GRANT SELECT ON TABLE identity.v_person_primary_contact TO exam_sys_readonly;
GRANT SELECT ON TABLE identity.v_person_primary_address TO exam_sys_readonly;
GRANT SELECT ON TABLE academic.v_student_consent_status TO exam_sys_readonly;

-- App role keeps full access to source tables and views.
GRANT SELECT ON TABLE academic.v_student_accessibility_exam_accommodation TO exam_sys_app;
GRANT SELECT ON TABLE academic.v_student_learning_context_summary TO exam_sys_app;
GRANT SELECT ON TABLE identity.v_person_primary_contact TO exam_sys_app;
GRANT SELECT ON TABLE identity.v_person_primary_address TO exam_sys_app;
GRANT SELECT ON TABLE academic.v_student_consent_status TO exam_sys_app;
