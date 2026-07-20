-- Migration 001: Initial Database Schema
-- Date: 2024-01-01
-- Description: Creates initial database tables for attendance system

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    moodle_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    aadhaar_number TEXT UNIQUE,
    student_id TEXT UNIQUE,
    phone_number TEXT,
    profile_pic TEXT,
    is_active BOOLEAN DEFAULT 1,
    verification_status TEXT DEFAULT 'PENDING',
    failed_login_attempts INTEGER DEFAULT 0,
    last_login DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Admins table
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE,
    role TEXT DEFAULT 'admin',
    is_active BOOLEAN DEFAULT 1,
    last_login DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Events table
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    venue TEXT DEFAULT '',
    max_capacity INTEGER DEFAULT 100,
    current_registrations INTEGER DEFAULT 0,
    registration_deadline DATETIME,
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    deleted_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES admins (id),
    FOREIGN KEY (deleted_by) REFERENCES admins (id)
);

-- Lectures table
CREATE TABLE IF NOT EXISTS lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    faculty TEXT NOT NULL,
    time TEXT NOT NULL,
    duration INTEGER DEFAULT 60,
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Event-Lecture association
CREATE TABLE IF NOT EXISTS event_lectures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    lecture_id INTEGER NOT NULL,
    sequence_order INTEGER DEFAULT 0,
    date DATE,
    start_time TIME,
    end_time TIME,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    FOREIGN KEY (lecture_id) REFERENCES lectures (id) ON DELETE CASCADE,
    UNIQUE(event_id, lecture_id)
);

-- Registrations table
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    qr_code TEXT,
    is_cancelled BOOLEAN DEFAULT 0,
    cancelled_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    UNIQUE(user_id, event_id)
);

-- Insert default admin
INSERT OR IGNORE INTO admins (username, password, email, role, created_at) 
VALUES ('admin', 'scrypt:32768:8:1$NHXavtWJrnSXQduR$c1b7e6d9c8a5b4f3e2d1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f', 'admin@example.com', 'super_admin', CURRENT_TIMESTAMP);

-- Insert default lecture
INSERT OR IGNORE INTO lectures (id, subject, faculty, time, duration, description, created_at)
VALUES (1, 'General Lecture', 'Default Faculty', '10:00', 60, 'Default lecture for testing', CURRENT_TIMESTAMP);

-- Update database version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);