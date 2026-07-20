-- Migration 010: Add verified column to users table
ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0;