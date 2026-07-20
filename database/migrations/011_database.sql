-- Migration 011: database
-- Date: 2026-02-19 16:08:07
-- Description: 

-- Write your migration SQL here
-- Example:
-- ALTER TABLE users ADD COLUMN new_column TEXT;

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (11);
