-- Phase 1.1 hardening
-- Add non-redundant indexes for high-usage foreign key lookup columns.

CREATE INDEX IF NOT EXISTS idx_app_user_person_id
    ON identity.app_user(person_id);

CREATE INDEX IF NOT EXISTS idx_user_role_role_id
    ON identity.user_role(role_id);

CREATE INDEX IF NOT EXISTS idx_student_profile_person_id
    ON identity.student_profile(person_id);

CREATE INDEX IF NOT EXISTS idx_student_profile_program_id
    ON identity.student_profile(program_id);

CREATE INDEX IF NOT EXISTS idx_instructor_profile_person_id
    ON identity.instructor_profile(person_id);

CREATE INDEX IF NOT EXISTS idx_instructor_profile_department_id
    ON identity.instructor_profile(department_id);

CREATE INDEX IF NOT EXISTS idx_contact_point_person_id
    ON identity.contact_point(person_id);

CREATE INDEX IF NOT EXISTS idx_address_person_id
    ON identity.address(person_id);

CREATE INDEX IF NOT EXISTS idx_program_department_id
    ON academic.program(department_id);

CREATE INDEX IF NOT EXISTS idx_course_department_id
    ON academic.course(department_id);

CREATE INDEX IF NOT EXISTS idx_course_offering_course_id
    ON academic.course_offering(course_id);

CREATE INDEX IF NOT EXISTS idx_course_offering_term_id
    ON academic.course_offering(term_id);

CREATE INDEX IF NOT EXISTS idx_course_offering_coordinator_id
    ON academic.course_offering(coordinator_id);

CREATE INDEX IF NOT EXISTS idx_class_section_course_offering_id
    ON academic.class_section(course_offering_id);

CREATE INDEX IF NOT EXISTS idx_class_enrollment_student_id
    ON academic.class_enrollment(student_id);

CREATE INDEX IF NOT EXISTS idx_teaching_assignment_instructor_id
    ON academic.teaching_assignment(instructor_id);

CREATE INDEX IF NOT EXISTS idx_student_demographic_profile_student_id
    ON academic.student_demographic_profile(student_id);

CREATE INDEX IF NOT EXISTS idx_student_prior_education_student_id
    ON academic.student_prior_education(student_id);

CREATE INDEX IF NOT EXISTS idx_student_socioeconomic_profile_student_id
    ON academic.student_socioeconomic_profile(student_id);

CREATE INDEX IF NOT EXISTS idx_student_learning_context_student_id
    ON academic.student_learning_context(student_id);

CREATE INDEX IF NOT EXISTS idx_student_accessibility_profile_student_id
    ON academic.student_accessibility_profile(student_id);

CREATE INDEX IF NOT EXISTS idx_student_accessibility_profile_approved_by
    ON academic.student_accessibility_profile(approved_by);

CREATE INDEX IF NOT EXISTS idx_student_consent_student_id
    ON academic.student_consent(student_id);
