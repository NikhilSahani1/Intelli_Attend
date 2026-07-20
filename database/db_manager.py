"""
Database Manager for Intelligent Attendance System
Handles all database operations with connection pooling and transaction management
"""
import sqlite3
import os
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from flask import current_app, g

class DatabaseManager:
    """Thread-safe database manager with connection pooling"""
    
    _instances = {}
    _lock = threading.Lock()
    
    def __new__(cls, db_path=None):
        """Singleton pattern per database path"""
        if db_path not in cls._instances:
            with cls._lock:
                if db_path not in cls._instances:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instances[db_path] = instance
        return cls._instances[db_path]
    
    def __init__(self, db_path=None):
        """Initialize database manager"""
        if self._initialized:
            return
            
        if db_path is None:
            self.db_path = os.path.join(os.path.dirname(__file__), 'event_system.db')
        else:
            self.db_path = db_path
            
        self.pool = {}
        self.pool_size = 10
        self.timeout = 30
        self._initialized = True
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool"""
        thread_id = threading.get_ident()
        
        if thread_id not in self.pool:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=False,
                isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")
            
            self.pool[thread_id] = conn
        
        try:
            yield self.pool[thread_id]
        except Exception as e:
            self.pool[thread_id].rollback()
            raise e
        finally:
            pass
    
    @contextmanager
    def transaction(self):
        """Database transaction context manager"""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
    
    def execute(self, query, params=None):
        """Execute a query and return cursor"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            return cursor
    
    def execute_many(self, query, params_list):
        """Execute many queries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
    
    def fetch_one(self, query, params=None):
        """Fetch one row"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params or [])
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def fetch_all(self, query, params=None):
        """Fetch all rows"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params or [])
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def insert(self, table, data):
        """Insert a record"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, list(data.values()))
            conn.commit()
            return cursor.lastrowid
    
    def insert_many(self, table, data_list):
        """Insert multiple records"""
        if not data_list:
            return []
            
        columns = ', '.join(data_list[0].keys())
        placeholders = ', '.join(['?' for _ in data_list[0]])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        values_list = [list(data.values()) for data in data_list]
        
        with self.get_connection() as conn:
            cursor = conn.executemany(query, values_list)
            conn.commit()
            return cursor.lastrowid
    
    def update(self, table, data, where_clause, where_params):
        """Update records"""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, list(data.values()) + where_params)
            conn.commit()
            return cursor.rowcount
    
    def delete(self, table, where_clause, where_params):
        """Delete records"""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        
        with self.get_connection() as conn:
            cursor = conn.execute(query, where_params)
            conn.commit()
            return cursor.rowcount
    
    def table_exists(self, table_name):
        """Check if table exists"""
        result = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        return result is not None
    
    def column_exists(self, table_name, column_name):
        """Check if column exists in table"""
        columns = self.fetch_all(f"PRAGMA table_info({table_name})")
        return any(col['name'] == column_name for col in columns)
    
    def add_column(self, table_name, column_name, column_type):
        """Add a column to table if it doesn't exist"""
        if not self.column_exists(table_name, column_name):
            self.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            return True
        return False
    
    def get_table_info(self, table_name):
        """Get table schema information"""
        return self.fetch_all(f"PRAGMA table_info({table_name})")
    
    def get_table_count(self, table_name):
        """Get row count for a table"""
        result = self.fetch_one(f"SELECT COUNT(*) as count FROM {table_name}")
        return result['count'] if result else 0
    
    def backup(self, backup_path=None):
        """Create database backup"""
        if not backup_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(os.path.dirname(self.db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f'event_system_{timestamp}.db')
        
        with self.get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        
        return backup_path
    
    def vacuum(self):
        """Vacuum database"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
    
    def close_all(self):
        """Close all database connections"""
        for conn in self.pool.values():
            try:
                conn.close()
            except:
                pass
        self.pool.clear()
    
    def get_stats(self):
        """Get database statistics"""
        stats = {
            'tables': {},
            'total_size': 0,
            'connections': len(self.pool)
        }
        
        # Get list of all tables
        tables = self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        
        for table in tables:
            table_name = table['name']
            stats['tables'][table_name] = self.get_table_count(table_name)
        
        if os.path.exists(self.db_path):
            stats['total_size'] = os.path.getsize(self.db_path)
        
        return stats
    
    def execute_script(self, script):
        """Execute a SQL script"""
        with self.get_connection() as conn:
            conn.executescript(script)
            conn.commit()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add face enrollment columns (this will run every time but handles errors)
            self._add_face_columns(cursor)
            
            # Create events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    created_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            
            # Create attendance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'present',
                    FOREIGN KEY (event_id) REFERENCES events (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(event_id, user_id)
                )
            ''')
            
            conn.commit()
            print("Database initialized successfully")
    
    def _add_face_columns(self, cursor):
        """Add face enrollment columns to users table if they don't exist"""
        try:
            # Check existing columns
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'role' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
                print("Added role column")
            
            if 'face_enrolled' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN face_enrolled INTEGER DEFAULT 0")
                print("Added face_enrolled column")
            
            if 'face_image_path' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN face_image_path TEXT")
                print("Added face_image_path column")
            
            if 'updated_at' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                print("Added updated_at column")
                
        except Exception as e:
            print(f"Note: {e}")


# Flask integration functions
def get_db():
    """Get database connection for Flask context"""
    if 'db' not in g:
        g.db = DatabaseManager(current_app.config.get('DATABASE_PATH'))
    return g.db


def init_db(app):
    """Initialize database for Flask app"""
    db = DatabaseManager(app.config.get('DATABASE_PATH'))
    
    @app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close_all()
    
    return db


def close_db(error=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close_all()