-- Phase 1 source: docs/phase_1_database_architecture.md
-- Grants for runtime and readonly roles on newly created core tables.

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity TO exam_sys_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA academic TO exam_sys_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA identity TO exam_sys_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA academic TO exam_sys_app;

GRANT SELECT ON ALL TABLES IN SCHEMA identity TO exam_sys_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA academic TO exam_sys_readonly;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA identity TO exam_sys_readonly;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA academic TO exam_sys_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA identity
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO exam_sys_app;
ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA academic
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO exam_sys_app;

ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA identity
    GRANT SELECT ON TABLES TO exam_sys_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA academic
    GRANT SELECT ON TABLES TO exam_sys_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA identity
    GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_app;
ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA academic
    GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_app;

ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA identity
    GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE exam_sys_owner IN SCHEMA academic
    GRANT USAGE, SELECT ON SEQUENCES TO exam_sys_readonly;
