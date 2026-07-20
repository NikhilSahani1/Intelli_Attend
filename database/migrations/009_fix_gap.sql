-- Migration 009: Fix Gap
-- Date: 2026-02-19
-- Description: Dummy migration to fix version gap

-- This is an empty migration to fill the version gap
-- No actual schema changes needed

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (9);