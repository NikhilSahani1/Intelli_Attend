"""
Database utility functions for managing SQLite connections
"""
import sqlite3
import os
import threading
from flask import g
from datetime import datetime

# Thread-local storage for database connections
thread_local = threading.local()

def get_db():
    """Get database connection for current thread"""
    if not hasattr(thread_local, 'db_connection'):
        from flask import current_app
        db_path = current_app.config['DATABASE_PATH']
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        
        thread_local.db_connection = conn
    
    return thread_local.db_connection

def close_db(e=None):
    """Close database connection"""
    try:
        conn = getattr(thread_local, 'db_connection', None)
        if conn:
            conn.close()
            if hasattr(thread_local, 'db_connection'):
                delattr(thread_local, 'db_connection')
    except Exception:
        pass

def init_db(app):
    """Initialize database with all required tables"""
    db_path = app.config['DATABASE_PATH']
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Initializing database...")
    
    # Create tables
    create_tables(cursor)
    
    # Add columns if needed
    add_missing_columns(cursor)
    
    # Create default admin
    create_default_admin(cursor)
    
    # Create default lecture
    create_default_lecture(cursor)
    
    conn.commit()
    conn.close()
    
    print("Database initialization completed successfully")
    
    # Register teardown
    app.teardown_appcontext(close_db)

def create_tables(cursor):
    """Create all database tables"""
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            moodle_id TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            aadhaar_number TEXT UNIQUE,
            student_id TEXT UNIQUE,
            phone_number TEXT,
            is_active BOOLEAN DEFAULT 1,
            verification_status TEXT DEFAULT 'PENDING',
            failed_login_attempts INTEGER DEFAULT 0,
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            venue TEXT DEFAULT '',
            max_capacity INTEGER DEFAULT 100,
            current_registrations INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME,
            deleted_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES admins (id),
            FOREIGN KEY (deleted_by) REFERENCES admins (id)
        )
    ''')
    
    # Lectures table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            faculty TEXT NOT NULL,
            time TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Event-Lecture association table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            lecture_id INTEGER NOT NULL,
            sequence_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (event_id) REFERENCES events (id),
            FOREIGN KEY (lecture_id) REFERENCES lectures (id),
            UNIQUE(event_id, lecture_id)
        )
    ''')
    
    # Registrations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_id INTEGER,
            registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (event_id) REFERENCES events (id),
            UNIQUE(user_id, event_id)
        )
    ''')
    
    # Attendance table with fraud detection fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_id INTEGER,
            lecture_id INTEGER DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            verification_type TEXT DEFAULT 'QR',
            verified_by INTEGER,
            fraud_score REAL DEFAULT 0.0,
            fraud_flags TEXT,
            face_encoding TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (event_id) REFERENCES events (id),
            FOREIGN KEY (lecture_id) REFERENCES lectures (id),
            FOREIGN KEY (verified_by) REFERENCES admins (id)
        )
    ''')
    
    # ID Verification table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS id_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            id_type TEXT NOT NULL,
            id_number TEXT NOT NULL,
            verified_by INTEGER,
            verified_at DATETIME,
            status TEXT DEFAULT 'PENDING',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (verified_by) REFERENCES admins (id)
        )
    ''')
    
    # Audit log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            description TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Face encodings table (for ML)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            encoding BLOB NOT NULL,
            quality_score REAL,
            enrolled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

def table_has_column(cursor, table_name, column_name):
    """Check if a table has a specific column"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_missing_columns(cursor):
    """Add missing columns to existing tables"""
    
    # Columns to add: (table, column, definition)
    columns_to_add = [
        # Users table
        ("users", "aadhaar_number", "TEXT"),
        ("users", "student_id", "TEXT"),
        ("users", "phone_number", "TEXT"),
        ("users", "verification_status", "TEXT DEFAULT 'PENDING'"),
        ("users", "failed_login_attempts", "INTEGER DEFAULT 0"),
        
        # Attendance table
        ("attendance", "fraud_score", "REAL DEFAULT 0.0"),
        ("attendance", "fraud_flags", "TEXT"),
        ("attendance", "face_encoding", "TEXT"),
        
        # Events table
        ("events", "venue", "TEXT DEFAULT ''"),
        ("events", "max_capacity", "INTEGER DEFAULT 100"),
        ("events", "current_registrations", "INTEGER DEFAULT 0"),
    ]
    
    for table, column, definition in columns_to_add:
        try:
            if not table_has_column(cursor, table, column):
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                print(f"✓ Added column {column} to {table}")
        except Exception as e:
            print(f"✗ Failed to add column {column} to {table}: {e}")

def create_default_admin(cursor):
    """Create default admin if not exists"""
    from werkzeug.security import generate_password_hash
    
    cursor.execute("SELECT id FROM admins WHERE username = ?", ('admin',))
    if not cursor.fetchone():
        hashed = generate_password_hash('Admin@123')
        cursor.execute('''
            INSERT INTO admins (username, password, is_active, created_at)
            VALUES (?, ?, ?, ?)
        ''', ('admin', hashed, 1, datetime.now()))
        print("✓ Default admin created (username=admin, password=Admin@123)")

def create_default_lecture(cursor):
    """Create default lecture if not exists"""
    cursor.execute("SELECT id FROM lectures WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO lectures (id, subject, faculty, time, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (1, 'Default Lecture', 'Default Faculty', '10:00', 1, datetime.now()))
        print("✓ Default lecture created (id=1)")