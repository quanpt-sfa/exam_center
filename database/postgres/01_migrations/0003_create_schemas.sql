-- Phase 1 source: docs/phase_1_database_architecture.md
-- Required schemas: identity, academic
-- Optional schema in source design: ref (not created in this minimal foundation step)

CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS academic;
CREATE SCHEMA IF NOT EXISTS app_meta;

COMMENT ON SCHEMA identity IS 'Identity domain schema: person, app_user, roles, student/instructor profiles, contact.';
COMMENT ON SCHEMA academic IS 'Academic domain schema: department, program, term, course, class, enrollment, learning context.';
COMMENT ON SCHEMA app_meta IS 'Application metadata schema for schema migration tracking.';

ALTER SCHEMA identity OWNER TO exam_sys_owner;
ALTER SCHEMA academic OWNER TO exam_sys_owner;
ALTER SCHEMA app_meta OWNER TO exam_sys_owner;

GRANT USAGE ON SCHEMA identity TO exam_sys_app;
GRANT USAGE ON SCHEMA academic TO exam_sys_app;
GRANT USAGE ON SCHEMA app_meta TO exam_sys_app;

GRANT USAGE ON SCHEMA identity TO exam_sys_readonly;
GRANT USAGE ON SCHEMA academic TO exam_sys_readonly;
GRANT USAGE ON SCHEMA app_meta TO exam_sys_readonly;

GRANT CREATE ON SCHEMA identity TO exam_sys_owner;
GRANT CREATE ON SCHEMA academic TO exam_sys_owner;
GRANT CREATE ON SCHEMA app_meta TO exam_sys_owner;
