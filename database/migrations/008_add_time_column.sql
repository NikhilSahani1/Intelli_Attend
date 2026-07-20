-- Migration 008: Add time column to events table
ALTER TABLE events ADD COLUMN time TIME;