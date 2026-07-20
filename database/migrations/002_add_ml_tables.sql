-- Migration 002: Add ML and Fraud Detection Tables
-- Date: 2024-01-15
-- Description: Adds tables for ML models and fraud detection

-- Attendance table with fraud detection fields
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    lecture_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    location TEXT,
    verification_type TEXT DEFAULT 'QR',
    verified_by INTEGER,
    face_encoding TEXT,
    face_verified BOOLEAN DEFAULT 0,
    fraud_score REAL DEFAULT 0.0,
    fraud_flags TEXT,
    is_suspicious BOOLEAN DEFAULT 0,
    review_status TEXT DEFAULT 'PENDING',
    reviewed_by INTEGER,
    reviewed_at DATETIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    FOREIGN KEY (lecture_id) REFERENCES lectures (id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES admins (id),
    FOREIGN KEY (reviewed_by) REFERENCES admins (id)
);

-- Face encodings table
CREATE TABLE IF NOT EXISTS face_encodings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    encoding BLOB NOT NULL,
    encoding_json TEXT,
    quality_score REAL,
    image_path TEXT,
    enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used DATETIME,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- Fraud alerts table
CREATE TABLE IF NOT EXISTS fraud_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attendance_id INTEGER,
    user_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT DEFAULT 'MEDIUM',
    description TEXT,
    fraud_score REAL,
    metadata TEXT,
    status TEXT DEFAULT 'NEW' CHECK(status IN ('NEW', 'INVESTIGATING', 'RESOLVED', 'FALSE_POSITIVE')),
    resolved_by INTEGER,
    resolved_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attendance_id) REFERENCES attendance (id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (resolved_by) REFERENCES admins (id)
);

-- ML Models table
CREATE TABLE IF NOT EXISTS ml_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    version TEXT,
    accuracy REAL,
    trained_on DATETIME,
    trained_by INTEGER,
    model_path TEXT,
    parameters TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trained_by) REFERENCES admins (id)
);

-- Training logs table
CREATE TABLE IF NOT EXISTS training_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    samples_used INTEGER,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    training_time REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES ml_models (id)
);

-- Anomaly patterns table
CREATE TABLE IF NOT EXISTS anomaly_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,
    pattern_data TEXT,
    frequency INTEGER DEFAULT 1,
    risk_level TEXT,
    first_detected DATETIME,
    last_detected DATETIME,
    occurrences INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT 1
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_attendance_user_id ON attendance(user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_event_id ON attendance(event_id);
CREATE INDEX IF NOT EXISTS idx_attendance_timestamp ON attendance(timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_fraud_score ON attendance(fraud_score);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_user_id ON fraud_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_fraud_alerts_status ON fraud_alerts(status);

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (2);