# backend/database/migrations/add_face_columns.py

import sqlite3
import os
import sys

# Add parent directory to path so we can import db_manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def add_face_columns():
    """Add face enrollment columns to users table"""
    
    # Path to your database
    db_path = os.path.join(os.path.dirname(__file__), '..', 'event_system.db')
    db_path = os.path.abspath(db_path)
    
    print(f"Connecting to database at: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current columns
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add face_enrolled column
        if 'face_enrolled' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN face_enrolled INTEGER DEFAULT 0")
            print("✅ Added column: face_enrolled")
        else:
            print("⏭️ Column 'face_enrolled' already exists")
        
        # Add face_image_path column
        if 'face_image_path' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN face_image_path TEXT")
            print("✅ Added column: face_image_path")
        else:
            print("⏭️ Column 'face_image_path' already exists")
        
        # Add updated_at column
        if 'updated_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("✅ Added column: updated_at")
        else:
            print("⏭️ Column 'updated_at' already exists")
        
        # Commit changes
        conn.commit()
        
        # Verify columns were added
        cursor.execute("PRAGMA table_info(users)")
        updated_columns = [column[1] for column in cursor.fetchall()]
        print(f"\nUpdated columns: {updated_columns}")
        
        conn.close()
        print("\n✅ Database migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_face_columns()