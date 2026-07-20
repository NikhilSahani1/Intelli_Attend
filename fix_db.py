import sqlite3
import os

# Find your database file
db_path = r"c:\Users\NIKHIL\OneDrive\Desktop\AMS\backend\attendance.db"

# If not there, try other common locations
if not os.path.exists(db_path):
    db_path = r"c:\Users\NIKHIL\OneDrive\Desktop\AMS\attendance.db"
if not os.path.exists(db_path):
    db_path = r"c:\Users\NIKHIL\OneDrive\Desktop\AMS\backend\instance\attendance.db"

print(f"Looking for database at: {db_path}")

if not os.path.exists(db_path):
    print("❌ Database file not found! Creating new one...")
    db_path = r"c:\Users\NIKHIL\OneDrive\Desktop\AMS\backend\attendance.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create the missing table
cursor.execute('''
CREATE TABLE IF NOT EXISTS event_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    lecture_name TEXT NOT NULL,
    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    face_verified BOOLEAN DEFAULT 0,
    liveness_score REAL DEFAULT 0,
    location_verified BOOLEAN DEFAULT 0,
    latitude REAL,
    longitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Also create lecture_attendance table
cursor.execute('''
CREATE TABLE IF NOT EXISTS lecture_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    lecture_name TEXT NOT NULL,
    attendance_date DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'present',
    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
print("✅ Tables created successfully!")

# Show all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("\n📋 Existing tables:")
for table in tables:
    print(f"   - {table[0]}")

conn.close()