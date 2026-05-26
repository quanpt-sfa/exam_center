-- Phase 2.1 source: docs/phase_2_assessment_generator_pipeline.md
-- Seeds assessment type lookup values idempotently.

INSERT INTO assessment.assessment_type (type_code, type_name, description, is_active)
VALUES
    ('QUIZ', 'Quiz', 'Short in-term assessment.', true),
    ('PRACTICE', 'Practice', 'Practice assessment used for learning reinforcement.', true),
    ('MIDTERM', 'Midterm', 'Midterm examination.', true),
    ('FINAL', 'Final', 'Final examination.', true),
    ('RETAKE', 'Retake', 'Retake assessment.', true),
    ('MAKEUP', 'Makeup', 'Makeup assessment.', true)
ON CONFLICT (type_code) DO UPDATE
SET
    type_name = EXCLUDED.type_name,
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active;