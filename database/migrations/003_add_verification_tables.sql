-- Migration 003: Add Verification Tables
-- Date: 2024-02-01
-- Description: Adds tables for ID verification and document management

-- ID Verification table
CREATE TABLE IF NOT EXISTS id_verification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    id_type TEXT NOT NULL CHECK(id_type IN ('MOODLE', 'AADHAAR', 'STUDENT_ID', 'OTHER')),
    id_number TEXT NOT NULL,
    document_path TEXT,
    verified_by INTEGER,
    verified_at DATETIME,
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'VERIFIED', 'REJECTED')),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES admins (id)
);

-- Verification history table
CREATE TABLE IF NOT EXISTS verification_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT,
    changed_by INTEGER,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    FOREIGN KEY (verification_id) REFERENCES id_verification (id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES admins (id)
);

-- Create trigger for verification history
CREATE TRIGGER IF NOT EXISTS verification_status_change
AFTER UPDATE OF status ON id_verification
BEGIN
    INSERT INTO verification_history (verification_id, old_status, new_status, changed_by, changed_at)
    VALUES (OLD.id, OLD.status, NEW.status, NEW.verified_by, CURRENT_TIMESTAMP);
END;

-- Add verification columns to users table
ALTER TABLE users ADD COLUMN id_verified BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN verified_at DATETIME;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_id_verification_user_id ON id_verification(user_id);
CREATE INDEX IF NOT EXISTS idx_id_verification_status ON id_verification(status);
CREATE INDEX IF NOT EXISTS idx_id_verification_id_type ON id_verification(id_type);

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (3);