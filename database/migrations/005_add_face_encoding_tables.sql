-- Migration 005: Enhanced Face Recognition Tables
-- Date: 2024-03-01
-- Description: Adds enhanced tables for face recognition and biometric data

-- Face recognition logs
CREATE TABLE IF NOT EXISTS face_recognition_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    attendance_id INTEGER,
    confidence REAL,
    match_score REAL,
    processing_time REAL,
    image_quality REAL,
    lighting_condition TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT 1,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (attendance_id) REFERENCES attendance (id) ON DELETE SET NULL
);

-- Face quality metrics
CREATE TABLE IF NOT EXISTS face_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    encoding_id INTEGER,
    brightness REAL,
    sharpness REAL,
    contrast REAL,
    face_size REAL,
    face_position_x REAL,
    face_position_y REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (encoding_id) REFERENCES face_encodings (id) ON DELETE CASCADE
);

-- Multiple face encodings per user (for different angles/lighting)
ALTER TABLE face_encodings ADD COLUMN angle TEXT DEFAULT 'front';
ALTER TABLE face_encodings ADD COLUMN lighting TEXT DEFAULT 'normal';
ALTER TABLE face_encodings ADD COLUMN glasses BOOLEAN DEFAULT 0;
ALTER TABLE face_encodings ADD COLUMN expression TEXT DEFAULT 'neutral';
ALTER TABLE face_encodings ADD COLUMN version INTEGER DEFAULT 1;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_face_recognition_logs_user_id ON face_recognition_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_face_recognition_logs_timestamp ON face_recognition_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_face_quality_metrics_user_id ON face_quality_metrics(user_id);

-- Update schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (5);