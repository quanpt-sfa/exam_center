-- Phase 1 source: docs/phase_1_database_architecture.md
-- Adds foreign keys after all core tables are created.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_app_user_person') THEN
        ALTER TABLE identity.app_user
            ADD CONSTRAINT fk_identity_app_user_person
            FOREIGN KEY (person_id)
            REFERENCES identity.person(person_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_user_role_user') THEN
        ALTER TABLE identity.user_role
            ADD CONSTRAINT fk_identity_user_role_user
            FOREIGN KEY (user_id)
            REFERENCES identity.app_user(user_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_user_role_role') THEN
        ALTER TABLE identity.user_role
            ADD CONSTRAINT fk_identity_user_role_role
            FOREIGN KEY (role_id)
            REFERENCES identity.role(role_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_user_role_assigned_by') THEN
        ALTER TABLE identity.user_role
            ADD CONSTRAINT fk_identity_user_role_assigned_by
            FOREIGN KEY (assigned_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_department_parent') THEN
        ALTER TABLE academic.department
            ADD CONSTRAINT fk_academic_department_parent
            FOREIGN KEY (parent_department_id)
            REFERENCES academic.department(department_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_program_department') THEN
        ALTER TABLE academic.program
            ADD CONSTRAINT fk_academic_program_department
            FOREIGN KEY (department_id)
            REFERENCES academic.department(department_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_student_profile_person') THEN
        ALTER TABLE identity.student_profile
            ADD CONSTRAINT fk_identity_student_profile_person
            FOREIGN KEY (person_id)
            REFERENCES identity.person(person_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_student_profile_program') THEN
        ALTER TABLE identity.student_profile
            ADD CONSTRAINT fk_identity_student_profile_program
            FOREIGN KEY (program_id)
            REFERENCES academic.program(program_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_instructor_profile_person') THEN
        ALTER TABLE identity.instructor_profile
            ADD CONSTRAINT fk_identity_instructor_profile_person
            FOREIGN KEY (person_id)
            REFERENCES identity.person(person_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_instructor_profile_department') THEN
        ALTER TABLE identity.instructor_profile
            ADD CONSTRAINT fk_identity_instructor_profile_department
            FOREIGN KEY (department_id)
            REFERENCES academic.department(department_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_contact_point_person') THEN
        ALTER TABLE identity.contact_point
            ADD CONSTRAINT fk_identity_contact_point_person
            FOREIGN KEY (person_id)
            REFERENCES identity.person(person_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_identity_address_person') THEN
        ALTER TABLE identity.address
            ADD CONSTRAINT fk_identity_address_person
            FOREIGN KEY (person_id)
            REFERENCES identity.person(person_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_course_department') THEN
        ALTER TABLE academic.course
            ADD CONSTRAINT fk_academic_course_department
            FOREIGN KEY (department_id)
            REFERENCES academic.department(department_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_course_offering_course') THEN
        ALTER TABLE academic.course_offering
            ADD CONSTRAINT fk_academic_course_offering_course
            FOREIGN KEY (course_id)
            REFERENCES academic.course(course_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_course_offering_term') THEN
        ALTER TABLE academic.course_offering
            ADD CONSTRAINT fk_academic_course_offering_term
            FOREIGN KEY (term_id)
            REFERENCES academic.term(term_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_course_offering_coordinator') THEN
        ALTER TABLE academic.course_offering
            ADD CONSTRAINT fk_academic_course_offering_coordinator
            FOREIGN KEY (coordinator_id)
            REFERENCES identity.instructor_profile(instructor_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_class_section_course_offering') THEN
        ALTER TABLE academic.class_section
            ADD CONSTRAINT fk_academic_class_section_course_offering
            FOREIGN KEY (course_offering_id)
            REFERENCES academic.course_offering(course_offering_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_class_enrollment_class_section') THEN
        ALTER TABLE academic.class_enrollment
            ADD CONSTRAINT fk_academic_class_enrollment_class_section
            FOREIGN KEY (class_section_id)
            REFERENCES academic.class_section(class_section_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_class_enrollment_student') THEN
        ALTER TABLE academic.class_enrollment
            ADD CONSTRAINT fk_academic_class_enrollment_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_teaching_assignment_class_section') THEN
        ALTER TABLE academic.teaching_assignment
            ADD CONSTRAINT fk_academic_teaching_assignment_class_section
            FOREIGN KEY (class_section_id)
            REFERENCES academic.class_section(class_section_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_teaching_assignment_instructor') THEN
        ALTER TABLE academic.teaching_assignment
            ADD CONSTRAINT fk_academic_teaching_assignment_instructor
            FOREIGN KEY (instructor_id)
            REFERENCES identity.instructor_profile(instructor_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_teaching_assignment_assigned_by') THEN
        ALTER TABLE academic.teaching_assignment
            ADD CONSTRAINT fk_academic_teaching_assignment_assigned_by
            FOREIGN KEY (assigned_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_demographic_profile_student') THEN
        ALTER TABLE academic.student_demographic_profile
            ADD CONSTRAINT fk_academic_student_demographic_profile_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_prior_education_student') THEN
        ALTER TABLE academic.student_prior_education
            ADD CONSTRAINT fk_academic_student_prior_education_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_socioeconomic_profile_student') THEN
        ALTER TABLE academic.student_socioeconomic_profile
            ADD CONSTRAINT fk_academic_student_socioeconomic_profile_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_learning_context_student') THEN
        ALTER TABLE academic.student_learning_context
            ADD CONSTRAINT fk_academic_student_learning_context_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_accessibility_profile_student') THEN
        ALTER TABLE academic.student_accessibility_profile
            ADD CONSTRAINT fk_academic_student_accessibility_profile_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_accessibility_profile_approved_by') THEN
        ALTER TABLE academic.student_accessibility_profile
            ADD CONSTRAINT fk_academic_student_accessibility_profile_approved_by
            FOREIGN KEY (approved_by)
            REFERENCES identity.app_user(user_id)
            ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_academic_student_consent_student') THEN
        ALTER TABLE academic.student_consent
            ADD CONSTRAINT fk_academic_student_consent_student
            FOREIGN KEY (student_id)
            REFERENCES identity.student_profile(student_id)
            ON DELETE RESTRICT;
    END IF;
END
$$;
