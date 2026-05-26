-- Phase 1 source: docs/phase_1_database_architecture.md
-- Seed suggested roles idempotently.

INSERT INTO identity.role (role_code, role_name, description)
VALUES
    ('STUDENT', 'Student', 'Learner participating in classes and exams.'),
    ('INSTRUCTOR', 'Instructor', 'Teaching staff responsible for course delivery.'),
    ('ADMIN', 'Administrator', 'System administrator with broad operational access.'),
    ('ACADEMIC_OFFICER', 'Academic Officer', 'Academic operations and administration role.'),
    ('PROCTOR', 'Proctor', 'Exam proctoring and invigilation role.'),
    ('GRADER', 'Grader', 'Evaluation and grading role.')
ON CONFLICT (role_code) DO UPDATE
SET
    role_name = EXCLUDED.role_name,
    description = EXCLUDED.description;
