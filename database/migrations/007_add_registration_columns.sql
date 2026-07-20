-- Migration 007: Add Registration Columns
-- Date: 2024-01-01
-- Description: Add phone_number, moodle_id, aadhaar_number, student_id columns to users table

-- Add phone_number column
ALTER TABLE users ADD COLUMN phone_number TEXT;

-- Add moodle_id column (unique)
ALTER TABLE users ADD COLUMN moodle_id TEXT UNIQUE;

-- Add aadhaar_number column (unique)
ALTER TABLE users ADD COLUMN aadhaar_number TEXT UNIQUE;

-- Add student_id column (unique)
ALTER TABLE users ADD COLUMN student_id TEXT UNIQUE;

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (7);