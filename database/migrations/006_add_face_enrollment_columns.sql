-- backend/database/migrations/006_add_face_enrollment_columns.sql
-- Add face enrollment columns to users table

-- Add role column if it doesn't exist
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';

-- Add face_enrolled column
ALTER TABLE users ADD COLUMN face_enrolled INTEGER DEFAULT 0;

-- Add face_image_path column
ALTER TABLE users ADD COLUMN face_image_path TEXT;

-- Add updated_at column
ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;