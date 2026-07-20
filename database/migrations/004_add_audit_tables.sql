-- Migration 004: Add Audit and Security Tables
-- Date: 2024-02-15
-- Description: Adds tables for audit logging and security

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    description TEXT,
    ip_address TEXT,
    user_agent TEXT,
    resource_type TEXT,
    resource_id INTEGER,
    status TEXT DEFAULT 'SUCCESS',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    type TEXT DEFAULT 'string',
    description TEXT,
    updated_by INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES admins (id)
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT UNIQUE NOT NULL,
    user_type TEXT NOT NULL CHECK(user_type IN ('user', 'admin')),
    ip_address TEXT,
    user_agent TEXT,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME,
    expiry_time DATETIME,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Login attempts table for rate limiting
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,
    ip_address TEXT,
    success BOOLEAN DEFAULT 0,
    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- API keys table (for future API development)
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    key TEXT UNIQUE NOT NULL,
    permissions TEXT,
    last_used DATETIME,
    expires_at DATETIME,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_login_attempts_identifier ON login_attempts(identifier);
CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key);

-- Insert default settings
INSERT OR IGNORE INTO settings (key, value, type, description) VALUES 
    ('fraud_detection_enabled', 'true', 'boolean', 'Enable/disable fraud detection'),
    ('fraud_threshold', '0.6', 'float', 'Threshold for fraud detection'),
    ('face_recognition_enabled', 'true', 'boolean', 'Enable/disable face recognition'),
    ('auto_cleanup_days', '30', 'integer', 'Days to keep attendance records'),
    ('session_timeout', '7200', 'integer', 'Session timeout in seconds'),
    ('max_login_attempts', '5', 'integer', 'Maximum login attempts before lockout'),
    ('lockout_time', '900', 'integer', 'Lockout time in seconds'),
    ('company_name', 'IntelliAttend', 'string', 'Company/Organization name'),
    ('enable_email_notifications', 'true', 'boolean', 'Enable email notifications'),
    ('maintenance_mode', 'false', 'boolean', 'Put system in maintenance mode');

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (4);