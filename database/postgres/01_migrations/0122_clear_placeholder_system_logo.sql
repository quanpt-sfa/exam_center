-- Migration to clear placeholder system logo if it exists
UPDATE ops.system_settings
SET portal_logo_url = NULL
WHERE portal_logo_url = 'https://example.com/logo.png';
