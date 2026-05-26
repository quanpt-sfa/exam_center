ALTER TABLE assessment.question_grading_profile
    DROP CONSTRAINT IF EXISTS ck_assessment_question_grading_profile_input_source;

ALTER TABLE assessment.question_grading_profile
    ADD CONSTRAINT ck_assessment_question_grading_profile_input_source CHECK (
        input_source IN (
            'SEALED_TEXT_ANSWER',
            'SEALED_JSON_ANSWER',
            'SEALED_FILE_REF',
            'STUDENT_DATABASE_CAPTURE',
            'MISA_DATABASE_CAPTURE',
            'AMIS_API_CAPTURE',
            'FILE_ARTIFACT_CAPTURE',
            'MANUAL'
        )
    );