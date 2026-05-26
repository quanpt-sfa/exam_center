-- Phase 1.1 hardening
-- Add partial unique indexes for primary records and current student context records.

CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_point_one_current_primary_per_type
    ON identity.contact_point(person_id, contact_type)
    WHERE is_primary = true AND valid_to IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_address_one_current_primary_per_type
    ON identity.address(person_id, address_type)
    WHERE is_primary = true AND valid_to IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_demographic_profile_one_current_per_student
    ON academic.student_demographic_profile(student_id)
    WHERE valid_to IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_socioeconomic_profile_one_current_per_student
    ON academic.student_socioeconomic_profile(student_id)
    WHERE valid_to IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_learning_context_one_current_per_student
    ON academic.student_learning_context(student_id)
    WHERE valid_to IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_student_accessibility_profile_one_current_per_student
    ON academic.student_accessibility_profile(student_id)
    WHERE valid_to IS NULL;

-- Prior education may contain multiple rows per student; keep it non-unique by design.
CREATE INDEX IF NOT EXISTS idx_student_prior_education_student_entry_year
    ON academic.student_prior_education(student_id, entry_year);

-- Consent is purpose-specific; add search index without enforcing global uniqueness.
CREATE INDEX IF NOT EXISTS idx_student_consent_lookup
    ON academic.student_consent(student_id, purpose_code, consent_type, consent_status);
