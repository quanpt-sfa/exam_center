-- Seed MVP import templates and CLI command registry.

INSERT INTO importing.import_template (
    template_code,
    template_name,
    schema_version,
    entity_code,
    is_active
)
VALUES
    ('STUDENT_V1', 'Student Import Template V1', 'V1', 'STUDENT', true),
    ('ENROLLMENT_V1', 'Enrollment Import Template V1', 'V1', 'ENROLLMENT', true)
ON CONFLICT (template_code) DO UPDATE
SET
    template_name = EXCLUDED.template_name,
    schema_version = EXCLUDED.schema_version,
    entity_code = EXCLUDED.entity_code,
    is_active = EXCLUDED.is_active;

INSERT INTO ops.agent_command (command_code, description, is_active)
VALUES
    ('IMPORT_VALIDATE', 'Validate import file in staging without commit.', true),
    ('IMPORT_DRY_RUN', 'Run parse/validate preview without commit.', true),
    ('IMPORT_COMMIT', 'Commit validated staging rows into domain entities.', true)
ON CONFLICT (command_code) DO UPDATE
SET
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active;

INSERT INTO ops.agent_permission_scope (scope_code, description, is_active)
VALUES
    ('IMPORT_VALIDATE', 'Allows import validation and preview.', true),
    ('IMPORT_COMMIT', 'Allows import commit execution.', true)
ON CONFLICT (scope_code) DO UPDATE
SET
    description = EXCLUDED.description,
    is_active = EXCLUDED.is_active;
