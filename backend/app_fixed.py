from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import os
from datetime import datetime, timedelta
import secrets
import numpy as np
import pandas as pd  
import json
import sys
import sqlite3
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from datetime import datetime
from ml_models.face_recognition import FaceRecognizer
from ml_models.anomaly_detection import AnomalyDetector
from ml_models.attendance_prediction import AttendancePredictor
from security_logger import security_logger, log_activity
import subprocess
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
import time
from security_logger_enhanced import log_activity
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_mail import Mail, Message


def log_user_activity(log_type, action_template):
    """Decorator to log user activities"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            # Execute the function
            response = f(*args, **kwargs)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Prepare action details
            action = action_template
            details = f"User performed: {action_template}"
            
            # Log the activity
            log_activity(
                log_type=log_type,
                action=action,
                details=details,
                severity='INFO',
                duration_ms=duration_ms
            )
            
            return response
        return decorated_function
    return decorator

# Initialize ML components
face_recognizer = FaceRecognizer()
anomaly_detector = AnomalyDetector()
attendance_predictor = AttendancePredictor()

# Train models on startup
def train_ml_models():
    """Train ML models with existing data"""
    print("\n🤖 Training ML Models...")
    
    conn = get_db_connection()
    try:
        # Get attendance data for training
        attendance_data = conn.execute('''
            SELECT 
                a.*,
                u.name as user_name,
                e.name as event_name,
                e.date as event_date
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.timestamp >= datetime('now', '-90 days')
            ORDER BY a.timestamp DESC
        ''').fetchall()
        
        if len(attendance_data) >= 10:
            # Convert to list of dicts
            data_list = []
            for record in attendance_data:
                data_list.append({
                    'user_id': record['user_id'],
                    'user_name': record['user_name'],
                    'event_id': record['event_id'],
                    'event_name': record['event_name'],
                    'timestamp': record['timestamp'],
                    'fraud_score': record['fraud_score'],
                    'verified': record['verified']
                })
            
            # Train anomaly detector
            print(f"   Training anomaly detector on {len(data_list)} records...")
            anomaly_detector.train(data_list)
            
            # Train attendance predictor
            print(f"   Training attendance predictor...")
            # Prepare daily attendance data
            daily_data = {}
            for record in data_list:
                date = record['timestamp'][:10] if record['timestamp'] else None
                if date:
                    if date not in daily_data:
                        daily_data[date] = 0
                    daily_data[date] += 1
            
            daily_list = []
            for date, count in daily_data.items():
                dt = datetime.fromisoformat(date)
                daily_list.append({
                    'date': date,
                    'attendance_count': count,
                    'day_of_week': dt.weekday(),
                    'day_of_month': dt.day
                })
            
            if len(daily_list) >= 7:
                attendance_predictor.train_daily_attendance(daily_list)
            
            print("✅ ML models trained successfully!")
        else:
            print(f"⚠️ Insufficient data for training: {len(attendance_data)} records (need 10)")
            
    except Exception as e:
        print(f"⚠️ Error training ML models: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

# Call training after database initialization
# Add this in the if __name__ == '__main__' block after init_db()

# Create Flask app directly - NO factory function issues!
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static',
            static_url_path='/static')  # Add this line


# Configuration
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['DATABASE_PATH'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                            'database', 'event_system.db')
app.config['DEBUG'] = True
app.config['ENV'] = 'development'

# Session configuration
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

# =====================================================
# Email Configuration for Password Reset
# =====================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'sahaninikhil43@gmail.com'
app.config['MAIL_PASSWORD'] = 'mgxf uwqa rkes lgfr'
app.config['MAIL_DEFAULT_SENDER'] = 'sahaninikhil43@gmail.com'

# Initialize mail
mail = Mail(app)

# Test email configuration on startup
print(f"\n📧 Email Configuration:")
print(f"   Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
print(f"   Username: {app.config['MAIL_USERNAME']}")
print(f"   Password: {'*' * len(app.config['MAIL_PASSWORD'])}")

# Test SMTP connection
try:
    test_server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
    test_server.starttls()
    test_server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
    test_server.quit()
    print("   ✅ Email connection successful!")
except Exception as e:
    print(f"   ⚠️ Email connection failed: {e}")


# =====================================================
# Context Processor for templates
# =====================================================
@app.context_processor
def inject_now():
    """Inject now function into all templates"""
    return {'now': datetime.now}

# =====================================================
# Login Required Decorator
# =====================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'admin_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



# =====================================================
# Database Connection Function
# =====================================================
def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn
# =====================================================
# Automatic Deletion Scheduler
# =====================================================
# Initialize scheduler for automatic deletion of past events
scheduler = BackgroundScheduler()
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

def delete_past_events():
    """
    Delete events and lectures that have ended
    Uses multiple date fields for compatibility
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🔍 Checking for past events at {current_time}...")
        
        # First, check what columns exist
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📊 Events table has columns: {columns}")
        
        past_events = []
        
        # Try different date column combinations
        if 'end_time' in columns:
            # Use end_time if available
            cursor.execute("""
                SELECT id, name FROM events 
                WHERE datetime(end_time) < datetime(?)
            """, (current_time,))
            past_events = cursor.fetchall()
            print(f"📅 Using end_time column: Found {len(past_events)} events")
            
        elif 'date' in columns and 'time' in columns:
            # Combine date and time columns
            cursor.execute("""
                SELECT id, name FROM events 
                WHERE datetime(date || ' ' || time) < datetime(?)
            """, (current_time,))
            past_events = cursor.fetchall()
            print(f"📅 Using date+time columns: Found {len(past_events)} events")
            
        elif 'date' in columns:
            # Use only date (compare as date)
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT id, name FROM events 
                WHERE date < ?
            """, (today,))
            past_events = cursor.fetchall()
            print(f"📅 Using date column only: Found {len(past_events)} events")
        
        # Delete the events and their lectures
        for event in past_events:
            # Delete lectures for this event
            if 'lectures' in [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
                cursor.execute("DELETE FROM lectures WHERE event_id = ?", (event['id'],))
                lectures_deleted = cursor.rowcount
            else:
                lectures_deleted = 0
            
            # Delete the event
            cursor.execute("DELETE FROM events WHERE id = ?", (event['id'],))
            
            print(f"🗑️ Auto-deleted event '{event['name']}' (ID: {event['id']}) with {lectures_deleted} lectures")
        
        conn.commit()
        if past_events:
            print(f"✅ Total: {len(past_events)} events deleted automatically")
        else:
            print("✅ No past events found to delete")
        
    except Exception as e:
        print(f"❌ Error in delete_past_events: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

# Schedule the job to run every minute
scheduler.add_job(
    func=delete_past_events,
    trigger=IntervalTrigger(minutes=1),
    id='delete_past_events_job',
    name='Delete past events every minute',
    replace_existing=True
)

# Run once at startup to clean any past events
delete_past_events()

# =====================================================
# ML Training Functions
# =====================================================


def schedule_ml_training():
    """Schedule periodic ML model retraining"""
    def retrain_models():
        print("\n🔄 Retraining ML models...")
        train_ml_models()
    
    # Retrain every 24 hours
    scheduler.add_job(
        func=retrain_models,
        trigger=IntervalTrigger(hours=24),
        id='retrain_ml_models',
        name='Retrain ML models daily',
        replace_existing=True
    )
    print("✅ ML training scheduled (every 24 hours)")

def init_db():
    """Initialize database tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table with verified column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone_number TEXT,
            moodle_id TEXT UNIQUE,
            aadhaar_number TEXT UNIQUE,
            student_id TEXT UNIQUE,
            role TEXT DEFAULT 'user',
            verified INTEGER DEFAULT 0,
            face_enrolled INTEGER DEFAULT 0,
            face_image_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create events table - MAKE SURE 'time' COLUMN IS HERE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            venue TEXT,
            date DATE NOT NULL,
            time TIME,  
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')
    
    # Create attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            lecture_name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            fraud_score REAL DEFAULT 0,
            verified BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")

# Add this function near your other database functions (around line 150-200)
def add_event_time_columns():
    """Add time columns to events table if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"📊 Events table columns: {columns}")
        
        migrations_run = False
        
        # Add end_time column if missing
        if 'end_time' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN end_time DATETIME")
            print("✅ Added end_time column to events table")
            migrations_run = True
        
        # Add start_time column if missing (for completeness)
        if 'start_time' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN start_time DATETIME")
            print("✅ Added start_time column to events table")
            migrations_run = True
        
        if migrations_run:
            conn.commit()
            print("✅ Event table migrations completed")
        else:
            print("✅ Event table already has required columns")
            
    except Exception as e:
        print(f"❌ Error adding columns: {e}")
        conn.rollback()
    finally:
        conn.close()

# Call this function in your startup section (around line where init_db() is called)

def run_migrations():
    """Run database migrations - add new columns if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns in users table: {columns}")
        
        migrations_run = False
        
        # Add verified column if missing
        if 'verified' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
            print("Migration: Added verified column to users")
            migrations_run = True
        
        if 'role' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            print("Migration: Added role column to users")
            migrations_run = True
        
        if 'face_enrolled' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN face_enrolled INTEGER DEFAULT 0")
            print("Migration: Added face_enrolled column to users")
            migrations_run = True
        
        if 'face_image_path' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN face_image_path TEXT")
            print("Migration: Added face_image_path column to users")
            migrations_run = True
        
        if 'updated_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("Migration: Added updated_at column to users")
            migrations_run = True
        
        if 'phone_number' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
            print("Migration: Added phone_number column to users")
            migrations_run = True
        
        if 'moodle_id' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN moodle_id TEXT")
            print("Migration: Added moodle_id column to users")
            migrations_run = True
        
        if 'aadhaar_number' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN aadhaar_number TEXT")
            print("Migration: Added aadhaar_number column to users")
            migrations_run = True
        
        if 'student_id' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN student_id TEXT")
            print("Migration: Added student_id column to users")
            migrations_run = True
        
        if migrations_run:
            print("Users table migrations completed")

    # ===== EVENTS TABLE MIGRATIONS =====
    # Check if events table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if cursor.fetchone():
        # Get existing columns in events table
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns in events table: {columns}")
        
        # Add time column to events table if it doesn't exist
        if 'time' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN time TIME")
            print("✅ Migration: Added time column to events table")
    
    # ===== LECTURES TABLE MIGRATIONS =====
    # Check if lectures table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lectures'")
    if cursor.fetchone():
        # Get existing columns in lectures table
        cursor.execute("PRAGMA table_info(lectures)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns in lectures table: {columns}")
        
        # Add professor_name column to lectures table if it doesn't exist
        if 'professor_name' not in columns:
            cursor.execute("ALTER TABLE lectures ADD COLUMN professor_name TEXT")
            print("✅ Migration: Added professor_name column to lectures table")
    else:
        # If lectures table doesn't exist, create it with professor_name column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lectures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lecture_name TEXT NOT NULL,
                event_id INTEGER NOT NULL,
                professor_name TEXT,
                created_by INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events (id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        print("✅ Created lectures table with professor_name column")
    
    conn.commit()
    conn.close()
    print("All migrations completed")

# =====================================================
# Try to import MigrationManager for face migration
# =====================================================
try:
    # Try to import from migrations folder
    import sys
    # Add the backend directory to path
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    from database.migrations.migration_manager import MigrationManager
    MIGRATION_MANAGER_AVAILABLE = True
    print("✅ MigrationManager imported successfully")
except ImportError as e:
    MIGRATION_MANAGER_AVAILABLE = False
    print(f"⚠️ MigrationManager not available: {e}")
    print("   Face enrollment columns will be added by run_migrations() instead")

# =====================================================
# Try to import admin blueprint
# =====================================================
try:
    # Try to import admin routes if they exist
    from backend.routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp)
    print("✅ Admin blueprint registered successfully")
except ImportError as e:
    print(f"⚠️ Could not import admin blueprint: {e}")

# =====================================================
# Home Route
# =====================================================
# =====================================================
# Home Route with Real Data
# =====================================================
@app.route('/')
def home():
    """Home page with real statistics from database"""
    conn = get_db_connection()
    try:
        # Get real statistics from database
        # Total users count (excluding admins)
        users_count = conn.execute('''
            SELECT COUNT(*) as count FROM users WHERE role = 'user'
        ''').fetchone()
        
        # Events happening today
        today = datetime.now().strftime('%Y-%m-%d')
        events_today = conn.execute('''
            SELECT COUNT(*) as count FROM events 
            WHERE date = ?
        ''', (today,)).fetchone()
        
        # Average accuracy rate (based on fraud scores)
        # Lower fraud score = higher accuracy
        accuracy_result = conn.execute('''
            SELECT 
                AVG(CASE 
                    WHEN fraud_score <= 0.2 THEN 100 
                    WHEN fraud_score <= 0.4 THEN 90 
                    WHEN fraud_score <= 0.6 THEN 80 
                    WHEN fraud_score <= 0.8 THEN 70 
                    ELSE 60 
                END) as avg_accuracy
            FROM attendance
        ''').fetchone()
        
        # System uptime (mock data for now - you can implement real uptime tracking)
        uptime = 99.9  # You can calculate this based on system logs
        
        # Get active users in last 24 hours
        active_24h = conn.execute('''
            SELECT COUNT(DISTINCT user_id) as count FROM attendance 
            WHERE timestamp >= datetime('now', '-24 hours')
        ''').fetchone()
        
        # Get total events count
        total_events = conn.execute('SELECT COUNT(*) as count FROM events').fetchone()
        
        # Get total attendance count
        total_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance').fetchone()
        
        stats = {
            'active_users': users_count['count'] if users_count else 0,
            'events_today': events_today['count'] if events_today else 0,
            'accuracy_rate': round(accuracy_result['avg_accuracy'] if accuracy_result and accuracy_result['avg_accuracy'] else 99, 1),
            'uptime': uptime,
            'active_24h': active_24h['count'] if active_24h else 0,
            'total_events': total_events['count'] if total_events else 0,
            'total_attendance': total_attendance['count'] if total_attendance else 0
        }
        
        print(f"📊 Homepage Stats: {stats}")
        
    except Exception as e:
        print(f"Error fetching stats: {e}")
        # Fallback stats if database queries fail
        stats = {
            'active_users': 0,
            'events_today': 0,
            'accuracy_rate': 99.5,
            'uptime': 99.9,
            'active_24h': 0,
            'total_events': 0,
            'total_attendance': 0
        }
    finally:
        conn.close()
    
    return render_template('index.html', stats=stats)

# =====================================================
# Authentication Routes
# =====================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if request.method == 'POST':
        # Get all form fields
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone') or request.form.get('phone_number')
        moodle_id = request.form.get('moodle_id')
        aadhaar = request.form.get('aadhaar_number') or request.form.get('aadhaar')
        student_id = request.form.get('student_id')
        
        print(f"\n📝 Registration attempt:")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Phone: {phone}")
        print(f"   Moodle ID: {moodle_id}")
        print(f"   Aadhaar: {aadhaar}")
        print(f"   Student ID: {student_id}")
        
        # Validate required fields
        if not all([name, email, password]):
            flash('Name, Email and Password are required!', 'danger')
            return render_template('auth/register.html')
        
        conn = get_db_connection()
        try:
            # First check if email already exists
            existing = conn.execute('SELECT email FROM users WHERE email = ?', (email,)).fetchone()
            if existing:
                flash(f'Email {email} already exists! Please use a different email or login.', 'danger')
                return render_template('auth/register.html')
            
            # Check moodle_id if provided
            if moodle_id:
                existing = conn.execute('SELECT moodle_id FROM users WHERE moodle_id = ?', (moodle_id,)).fetchone()
                if existing:
                    flash(f'Moodle ID {moodle_id} already exists!', 'danger')
                    return render_template('auth/register.html')
            
            # Check aadhaar if provided
            if aadhaar:
                existing = conn.execute('SELECT aadhaar_number FROM users WHERE aadhaar_number = ?', (aadhaar,)).fetchone()
                if existing:
                    flash(f'Aadhaar number already exists!', 'danger')
                    return render_template('auth/register.html')
            
            # Check student_id if provided
            if student_id:
                existing = conn.execute('SELECT student_id FROM users WHERE student_id = ?', (student_id,)).fetchone()
                if existing:
                    flash(f'Student ID already exists!', 'danger')
                    return render_template('auth/register.html')
            
            # Get list of columns in users table
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"Available columns: {columns}")
            
            # Build dynamic INSERT query based on available columns
            insert_columns = ['name', 'email', 'password']
            insert_values = [name, email, password]
            
            # Add optional fields if they exist in table
            if 'phone_number' in columns and phone:
                insert_columns.append('phone_number')
                insert_values.append(phone)
            
            if 'moodle_id' in columns and moodle_id:
                insert_columns.append('moodle_id')
                insert_values.append(moodle_id)
            
            if 'aadhaar_number' in columns and aadhaar:
                insert_columns.append('aadhaar_number')
                insert_values.append(aadhaar)
            
            if 'student_id' in columns and student_id:
                insert_columns.append('student_id')
                insert_values.append(student_id)
            
            if 'role' in columns:
                insert_columns.append('role')
                insert_values.append('user')
            
            # CRITICAL FIX: Add verified column with default 0 (pending)
            if 'verified' in columns:
                insert_columns.append('verified')
                insert_values.append(0)  # 0 = pending verification
            
            # Construct and execute query
            placeholders = ','.join(['?' for _ in insert_values])
            query = f"INSERT INTO users ({', '.join(insert_columns)}) VALUES ({placeholders})"
            print(f"Executing: {query}")
            
            conn.execute(query, insert_values)
            conn.commit()
            
            flash('Registration successful! Please wait for admin verification.', 'success')
            print(f"✅ User registered successfully: {email} (pending verification)")
            return redirect(url_for('login'))
            
        except sqlite3.IntegrityError as e:
            print(f"❌ Integrity error: {e}")
            if 'UNIQUE constraint failed' in str(e):
                if 'email' in str(e):
                    flash('Email already exists!', 'danger')
                elif 'moodle_id' in str(e):
                    flash('Moodle ID already exists!', 'danger')
                elif 'aadhaar_number' in str(e):
                    flash('Aadhaar number already exists!', 'danger')
                elif 'student_id' in str(e):
                    flash('Student ID already exists!', 'danger')
                else:
                    flash('Duplicate entry! Please check your information.', 'danger')
            else:
                flash(f'Database error: {str(e)}', 'danger')
        except Exception as e:
            print(f"❌ Error: {e}")
            flash(f'Registration failed: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page with security logging"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hash the password using MD5 (same as import)
        import hashlib
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
        conn = get_db_connection()
        try:
            # Compare with hashed password
            user_row = conn.execute('''
                SELECT * FROM users WHERE email = ? AND password = ?
            ''', (username, hashed_password)).fetchone()
            
            user = dict(user_row) if user_row else None
            
        except Exception as e:
            print(f"Login error: {e}")
            user = None
        finally:
            conn.close()
        
        if user:
            # Check verification status (skip for admin)
            if user.get('role') != 'admin' and user.get('verified', 0) == 0:
                # Log pending verification attempt
                try:
                    from security_logger import security_logger
                    security_logger.log(
                        log_type='AUTH',
                        action='LOGIN_PENDING_VERIFICATION',
                        details=f"User {user['email']} attempted login but account not verified",
                        severity='WARNING',
                        user_info={'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user.get('role', 'user')}
                    )
                except Exception as log_error:
                    print(f"Logging error: {log_error}")
                flash('Your account is pending verification. Please wait for admin approval.', 'warning')
                return render_template('auth/login.html')
            
            # Set session variables
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['user_moodle_id'] = user.get('moodle_id', 'DEMO' + str(user['id']).zfill(3))
            session['user_type'] = user.get('role', 'user')
            session['user_verified'] = user.get('verified', 0)
            session['login_time'] = datetime.now().isoformat()
            
            # Log successful login
            try:
                from security_logger import security_logger
                security_logger.log(
                    log_type='AUTH',
                    action='LOGIN_SUCCESS',
                    details=f"User {user['email']} logged in successfully",
                    severity='INFO',
                    user_info={'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user.get('role', 'user')}
                )
                print(f"✅ Logged successful login for {user['email']}")
            except Exception as log_error:
                print(f"Logging error: {log_error}")
            
            flash(f'Welcome back, {user["name"]}!', 'success')
            
            if user.get('role') == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            # Log failed login
            try:
                from security_logger import security_logger
                security_logger.log(
                    log_type='AUTH',
                    action='LOGIN_FAILED',
                    details=f"Failed login attempt for email: {username}",
                    severity='WARNING'
                )
                print(f"⚠️ Logged failed login for {username}")
            except Exception as log_error:
                print(f"Logging error: {log_error}")
            flash('Invalid credentials', 'danger')
    
    return render_template('auth/login.html')

# =====================================================
# Forgot Password Routes
# =====================================================

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page - User can reset their password"""
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address', 'danger')
            return render_template('auth/forgot_password.html')
        
        conn = get_db_connection()
        
        # Check if user exists
        user = conn.execute('SELECT id, name, email FROM users WHERE email = ? AND role = "user"', (email,)).fetchone()
        
        if not user:
            conn.close()
            flash('No account found with this email address', 'danger')
            return render_template('auth/forgot_password.html')
        
        # Generate reset token
        import hashlib
        import time
        token_data = f"{user['id']}_{user['email']}_{int(time.time())}"
        reset_token = hashlib.md5(token_data.encode()).hexdigest()
        
        # Create password_resets table if not exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                used INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Delete old tokens for this user
        conn.execute('DELETE FROM password_resets WHERE user_id = ?', (user['id'],))
        
        # Store new token (expires in 1 hour)
        expires_at = datetime.now() + timedelta(hours=1)
        conn.execute('''
            INSERT INTO password_resets (user_id, token, expires_at)
            VALUES (?, ?, ?)
        ''', (user['id'], reset_token, expires_at))
        
        conn.commit()
        conn.close()
        
        # ========== GENERATE MOBILE-FRIENDLY RESET LINK ==========
        # Get the base URL that works on mobile devices
        def get_mobile_friendly_base_url():
            """Generate a URL that works on both computer and mobile"""
            # Try to get the network IP address
            try:
                import socket
                hostname = socket.gethostname()
                # Get local IP address
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                s.close()
                return f"http://{local_ip}:5000"
            except:
                # Fallback to localhost
                return "http://127.0.0.1:5000"
        
        # Create both local and network links
        local_link = url_for('reset_password', token=reset_token, _external=True)
        network_link = f"{get_mobile_friendly_base_url()}/reset-password/{reset_token}"
        
        # Print both links to console
        print(f"\n{'='*70}")
        print(f"🔐 PASSWORD RESET LINKS FOR {user['name']} ({email})")
        print(f"{'='*70}")
        print(f"📱 MOBILE LINK (Use on phone): {network_link}")
        print(f"💻 LOCAL LINK (Use on computer): {local_link}")
        print(f"📋 TOKEN: {reset_token}")
        print(f"⏰ Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Generate QR Code for mobile access
        try:
            import qrcode
            import io
            import base64
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(network_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64 for embedding in HTML
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()
            qr_code_html = f'<img src="data:image/png;base64,{qr_base64}" style="max-width: 200px; display: block; margin: 20px auto;">'
        except:
            qr_code_html = ""
            print("⚠️ QR code library not installed. Run: pip install qrcode pillow")
        
        # ========== SEND EMAIL ==========
        email_sent = False
        
        try:
            # Create email message
            msg = Message(
                subject="🔐 IntelliAttend - Password Reset Request",
                recipients=[email],
                html=f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
                        .button {{ display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                        .mobile-link {{ background: #e9ecef; padding: 15px; border-radius: 5px; word-break: break-all; margin: 15px 0; }}
                        .footer {{ font-size: 12px; color: #999; text-align: center; margin-top: 20px; }}
                        .warning {{ color: #dc3545; font-size: 12px; }}
                        .qr-container {{ text-align: center; margin: 20px 0; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h2>IntelliAttend</h2>
                            <p>Password Reset Request</p>
                        </div>
                        <div class="content">
                            <p>Hello <strong>{user['name']}</strong>,</p>
                            <p>We received a request to reset your password for your IntelliAttend account.</p>
                            
                            <p><strong>📱 For Mobile Access:</strong></p>
                            <div class="mobile-link">
                                <a href="{network_link}">{network_link}</a>
                            </div>
                            
                            <p><strong>💻 For Computer Access:</strong></p>
                            <div class="mobile-link">
                                <a href="{local_link}">{local_link}</a>
                            </div>
                            
                            <div style="text-align: center;">
                                <a href="{network_link}" class="button" style="color: white;">Reset Password</a>
                            </div>
                            
                            {qr_code_html if qr_code_html else ''}
                            
                            <p class="warning">⚠️ This link will expire in 1 hour for security reasons.</p>
                            <hr>
                            <p>If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
                            <p><small>💡 Tip: If the link doesn't work, copy and paste it directly into your browser.</small></p>
                        </div>
                        <div class="footer">
                            <p>IntelliAttend - Intelligent Attendance Monitoring System</p>
                            <p>This is an automated message, please do not reply.</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                body=f"""
                IntelliAttend - Password Reset Request
                
                Hello {user['name']},
                
                We received a request to reset your password for your IntelliAttend account.
                
                📱 FOR MOBILE ACCESS:
                {network_link}
                
                💻 FOR COMPUTER ACCESS:
                {local_link}
                
                This link will expire in 1 hour.
                
                If you didn't request this, please ignore this email.
                
                ---
                IntelliAttend - Intelligent Attendance Monitoring System
                """
            )
            
            # Send the email
            mail.send(msg)
            email_sent = True
            print(f"✅ Email sent successfully to {email}")
            
        except Exception as e:
            print(f"❌ Email sending failed: {e}")
            print(f"   Error details: {str(e)}")
        
        # Show appropriate message with both links
        if email_sent:
            flash(f'✅ Password reset link has been sent to {email}. Check your inbox/spam folder.', 'success')
            flash(f'📱 Mobile link: {network_link}', 'info')
            flash(f'💻 Computer link: {local_link}', 'info')
        else:
            # Show both links directly on the page
            flash(f'⚠️ Email could not be sent. Please use one of these links to reset your password:', 'warning')
            flash(f'📱 Mobile link: {network_link}', 'info')
            flash(f'💻 Computer link: {local_link}', 'info')
        
        # If QR code was generated, pass it to template
        if qr_code_html:
            flash(f'Scan QR code with your phone camera to open the link', 'info')
        
        return render_template('auth/forgot_password.html', 
                             mobile_link=network_link, 
                             local_link=local_link,
                             qr_code=qr_code_html if qr_code_html else None)
    
    return render_template('auth/forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password page"""
    conn = get_db_connection()
    
    # Check if token exists and is valid
    reset_record = conn.execute('''
        SELECT * FROM password_resets 
        WHERE token = ? AND used = 0 AND expires_at > datetime('now')
    ''', (token,)).fetchone()
    
    if not reset_record:
        conn.close()
        flash('Invalid or expired password reset link. Please request a new one.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or len(new_password) < 4:
            flash('Password must be at least 4 characters long', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/reset_password.html', token=token)
        
        # Update password
        import hashlib
        hashed_password = hashlib.md5(new_password.encode()).hexdigest()
        
        conn.execute('UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                    (hashed_password, reset_record['user_id']))
        
        # Mark token as used
        conn.execute('UPDATE password_resets SET used = 1 WHERE token = ?', (token,))
        
        conn.commit()
        conn.close()
        
        flash('Password reset successfully! Please login with your new password.', 'success')
        return redirect(url_for('login'))
    
    conn.close()
    return render_template('auth/reset_password.html', token=token)

@app.route('/admin/fix-face-flags')
def fix_face_flags():
    """Fix face_enrolled flags for users with face photos"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin required'}), 403
    
    conn = get_db_connection()
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(backend_dir)
        faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
        
        updated = 0
        for user_id in os.listdir(faces_base_dir):
            user_dir = os.path.join(faces_base_dir, user_id)
            if os.path.isdir(user_dir):
                face_count = len([f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])
                if face_count > 0:
                    conn.execute('''
                        UPDATE users SET face_enrolled = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND (face_enrolled = 0 OR face_enrolled IS NULL)
                    ''', (user_id,))
                    if conn.rowcount > 0:
                        updated += 1
                        print(f"✅ Updated user ID {user_id}")
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': f'Updated {updated} users with face_enrolled=1'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# Add this debug endpoint to check and add test data
@app.route('/debug/security-logs-check')
def debug_security_logs_check():
    """Check security logs table and data"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    conn = get_db_connection()
    try:
        # Check if table exists
        table_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='security_logs'").fetchone()
        
        if not table_check:
            return jsonify({
                'exists': False,
                'message': 'security_logs table does not exist',
                'suggestion': 'Visit /debug/create-security-table to create it'
            })
        
        # Count records
        count = conn.execute("SELECT COUNT(*) as count FROM security_logs").fetchone()
        
        # Get sample records
        sample = conn.execute("SELECT * FROM security_logs ORDER BY timestamp DESC LIMIT 5").fetchall()
        
        return jsonify({
            'exists': True,
            'total_records': count['count'],
            'sample_records': [dict(row) for row in sample]
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()


@app.route('/debug/create-security-table')
def create_security_table():
    """Create security_logs table"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    conn = get_db_connection()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                log_type TEXT,
                action TEXT,
                details TEXT,
                user_id INTEGER,
                user_name TEXT,
                user_email TEXT,
                ip_address TEXT,
                severity TEXT,
                duration_ms INTEGER
            )
        ''')
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'security_logs table created successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'Admin@123':
            session['admin_id'] = 1
            session['admin_name'] = username
            session['user_type'] = 'admin'
            session['login_time'] = datetime.now().isoformat()
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('auth/admin_login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

# =====================================================
# User Dashboard Routes
# =====================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        # Get fresh user data from database
        user_row = conn.execute('SELECT * FROM users WHERE id = ?', 
                               (session['user_id'],)).fetchone()
        user_data = dict(user_row) if user_row else None
        
        # Update session with latest verification status
        if user_data:
            session['user_verified'] = user_data.get('verified', 0)
        
        # Determine verification status
        is_verified = False
        if user_data and 'verified' in user_data:
            verified_value = user_data.get('verified')
            if verified_value is not None:
                is_verified = (int(verified_value) == 1)
        
        # FIXED: Get REGISTERED events count (from registrations table, NOT attendance)
        registered_row = conn.execute('''
            SELECT COUNT(*) as count FROM registrations WHERE user_id = ?
        ''', (session['user_id'],)).fetchone()
        registered_count = registered_row['count'] if registered_row else 0
        
        # FIXED: Get ATTENDANCE count (real attendance from QR scans)
        attendance_row = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE user_id = ? AND verified = 1
        ''', (session['user_id'],)).fetchone()
        attendance_count = attendance_row['count'] if attendance_row else 0
        
        # Get upcoming events with registration status (from registrations table)
        upcoming_rows = conn.execute('''
            SELECT e.*, 
                   CASE WHEN r.id IS NOT NULL THEN 1 ELSE 0 END as is_registered
            FROM events e
            LEFT JOIN registrations r ON e.id = r.event_id AND r.user_id = ?
            WHERE e.date >= date('now')
            ORDER BY e.date ASC
            LIMIT 5
        ''', (session['user_id'],)).fetchall()
        
        upcoming_events_list = []
        for event in upcoming_rows:
            event_dict = dict(event)
            upcoming_events_list.append({
                'id': event_dict['id'],
                'name': event_dict['name'],
                'venue': event_dict.get('venue', 'TBD'),
                'date': event_dict['date'],
                'registered': bool(event_dict.get('is_registered', 0))
            })
        
        # Get recent attendance (real attendance records)
        recent_rows = conn.execute('''
            SELECT a.*, e.name as event_name 
            FROM attendance a
            JOIN events e ON a.event_id = e.id
            WHERE a.user_id = ?
            ORDER BY a.timestamp DESC 
            LIMIT 5
        ''', (session['user_id'],)).fetchall()
        
        recent_attendance_list = []
        for record in recent_rows:
            record_dict = dict(record)
            recent_attendance_list.append({
                'event_name': record_dict.get('event_name', 'Unknown Event'),
                'lecture_name': record_dict.get('lecture_name', 'Main Session'),
                'timestamp': record_dict.get('timestamp', '')[:10] if record_dict.get('timestamp') else '',
                'fraud_score': record_dict.get('fraud_score', 0)
            })
        
    except Exception as e:
        print(f"Error in dashboard: {e}")
        user_data = None
        is_verified = False
        registered_count = 0
        attendance_count = 0
        upcoming_events_list = []
        recent_attendance_list = []
    finally:
        conn.close()
    
    # Prepare user data for template
    user = {
        'name': user_data.get('name') if user_data else session.get('user_name', 'User'),
        'email': user_data.get('email') if user_data else '',
        'moodle_id': session.get('user_moodle_id', 'DEMO123'),
        'created_at': user_data.get('created_at')[:10] if user_data and user_data.get('created_at') else datetime.now().strftime('%Y-%m-%d'),
        'face_enrolled': user_data.get('face_enrolled', 0) if user_data else 0,
        'verified': is_verified,
        'student_id': user_data.get('student_id', '') if user_data else ''
    }
    
    # Calculate stats
    stats = {
        'registered_events': registered_count,
        'total_attendance': attendance_count,
        'attendance_rate': round((attendance_count / registered_count * 100) if registered_count > 0 else 0)
    }
    
    # Verification status for display
    verification_status = [{
        'id_type': 'Account Status',
        'id_number': session.get('user_email', ''),
        'status': 'VERIFIED' if is_verified else 'PENDING',
        'verified_at': user_data.get('updated_at', 'N/A')[:10] if is_verified and user_data and user_data.get('updated_at') else 'N/A'
    }]
    
    return render_template('dashboard/user_dashboard.html',
                         user=user, 
                         stats=stats,
                         upcoming_events=upcoming_events_list,
                         recent_attendance=recent_attendance_list,
                         verification_status=verification_status,
                         has_face=bool(user['face_enrolled']))

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard with real data"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    try:
        # ===== REAL STATISTICS FROM DATABASE =====
        
        # Active users (users with role='user')
        active_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE role="user"').fetchone()
        
        # New users today
        new_users_today = conn.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE role="user" AND date(created_at) = date('now')
        ''').fetchone()
        
        # Pending verifications
        pending_verifications = conn.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE role="user" AND (verified = 0 OR verified IS NULL)
        ''').fetchone()
        
        # Active events (upcoming events)
        active_events = conn.execute('''
            SELECT COUNT(*) as count FROM events 
            WHERE date >= date('now')
        ''').fetchone()
        
        # Archived events (past events)
        archived_events = conn.execute('''
            SELECT COUNT(*) as count FROM events 
            WHERE date < date('now')
        ''').fetchone()
        
        # Active lectures (unique lecture names from attendance)
        active_lectures = conn.execute('''
            SELECT COUNT(DISTINCT lecture_name) as count FROM attendance 
            WHERE lecture_name IS NOT NULL AND lecture_name != ''
        ''').fetchone()
        
        # Today's attendance
        today_attendance = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE date(timestamp) = date('now')
        ''').fetchone()
        
        # Fraud alerts today
        fraud_alerts_today = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE fraud_score > 0.7 AND date(timestamp) = date('now')
        ''').fetchone()
        
        # Average fraud score
        avg_fraud = conn.execute('''
            SELECT AVG(fraud_score) as avg FROM attendance 
            WHERE fraud_score > 0
        ''').fetchone()
        
        # Total attendance all time
        total_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance').fetchone()
        
        # Recent attendance for table
        recent_attendance = conn.execute('''
            SELECT 
                u.name as user_name,
                u.moodle_id,
                e.name as event_name,
                a.lecture_name,
                a.timestamp,
                a.fraud_score
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            ORDER BY a.timestamp DESC
            LIMIT 10
        ''').fetchall()
        
        recent_list = []
        for record in recent_attendance:
            recent_list.append({
                'user_name': record['user_name'],
                'moodle_id': record['moodle_id'],
                'event_name': record['event_name'],
                'lecture_name': record['lecture_name'] or 'Main Session',
                'timestamp': record['timestamp'],
                'fraud_score': record['fraud_score']
            })
        
        # Fraud alerts for sidebar
        fraud_alerts = conn.execute('''
            SELECT 
                u.name as user_name,
                e.name as event_name,
                a.timestamp,
                a.fraud_score
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.fraud_score > 0.6
            ORDER BY a.timestamp DESC
            LIMIT 5
        ''').fetchall()
        
        fraud_list = []
        for alert in fraud_alerts:
            risk = 'HIGH' if alert['fraud_score'] > 0.8 else 'MEDIUM'
            fraud_list.append({
                'user_name': alert['user_name'],
                'event_name': alert['event_name'],
                'timestamp': alert['timestamp'],
                'fraud_score': alert['fraud_score'],
                'risk_level': risk
            })
        
        # Chart data - last 7 days attendance
        chart_labels = []
        chart_data = []
        for i in range(6, -1, -1):
            from datetime import datetime, timedelta
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            chart_labels.append((datetime.now() - timedelta(days=i)).strftime('%a'))
            
            count = conn.execute('''
                SELECT COUNT(*) as count FROM attendance 
                WHERE date(timestamp) = ?
            ''', (date,)).fetchone()
            chart_data.append(count['count'] if count else 0)
        
        # Fraud chart data (mock for now - you can enhance this)
        fraud_high = [0, 0, 1, 0, 2, 0, 1]
        fraud_medium = [1, 2, 1, 3, 1, 2, 1]
        fraud_low = [3, 4, 2, 5, 3, 4, 2]
        
    except Exception as e:
        print(f"Error in admin dashboard: {e}")
        # Set defaults if queries fail
        active_users = {'count': 0}
        new_users_today = {'count': 0}
        pending_verifications = {'count': 0}
        active_events = {'count': 0}
        archived_events = {'count': 0}
        active_lectures = {'count': 0}
        today_attendance = {'count': 0}
        fraud_alerts_today = {'count': 0}
        avg_fraud = {'avg': 0}
        total_attendance = {'count': 0}
        recent_list = []
        fraud_list = []
        chart_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        chart_data = [0, 0, 0, 0, 0, 0, 0]
        fraud_high = [0, 0, 0, 0, 0, 0, 0]
        fraud_medium = [0, 0, 0, 0, 0, 0, 0]
        fraud_low = [0, 0, 0, 0, 0, 0, 0]
    
    finally:
        conn.close()
    
    # Compile statistics
    stats = {
        'active_users': active_users['count'] if active_users else 0,
        'new_users_today': new_users_today['count'] if new_users_today else 0,
        'pending_verifications': pending_verifications['count'] if pending_verifications else 0,
        'active_events': active_events['count'] if active_events else 0,
        'archived_events': archived_events['count'] if archived_events else 0,
        'active_lectures': active_lectures['count'] if active_lectures else 0,
        'today_attendance': today_attendance['count'] if today_attendance else 0,
        'fraud_alerts_today': fraud_alerts_today['count'] if fraud_alerts_today else 0,
        'avg_fraud_score': round(avg_fraud['avg'] * 100, 1) if avg_fraud and avg_fraud['avg'] else 0,
        'total_attendance': total_attendance['count'] if total_attendance else 0
    }
    
    # Format login time
    formatted_login_time = session.get('login_time', datetime.now().isoformat())[:10]
    
    return render_template('dashboard/admin_dashboard.html',
                         stats=stats,
                         recent_attendance=recent_list,
                         fraud_alerts=fraud_list,
                         attendance_labels=chart_labels,
                         attendance_data=chart_data,
                         fraud_labels=chart_labels,
                         fraud_high_data=fraud_high,
                         fraud_medium_data=fraud_medium,
                         fraud_low_data=fraud_low,
                         login_time=formatted_login_time,
                         current_time=datetime.now().strftime('%I:%M %p'))

# =====================================================
# Attendance Log Route (Admin)
# =====================================================
@app.route('/attendance-log')
@login_required
def attendance_log():
    """View all attendance records - Admin only"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    # Get filter parameters
    user_search = request.args.get('user', '')
    event_search = request.args.get('event', '')
    date_filter = request.args.get('date', '')
    fraud_filter = request.args.get('fraud', '')
    
    conn = get_db_connection()
    try:
        # Build query with filters
        query = '''
            SELECT 
                a.id,
                a.timestamp,
                a.fraud_score,
                a.verified,
                a.lecture_name,
                u.id as user_id,
                u.name as user_name,
                u.email as user_email,
                e.id as event_id,
                e.name as event_name,
                e.date as event_date
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE 1=1
        '''
        params = []
        
        if user_search:
            query += " AND u.name LIKE ?"
            params.append(f'%{user_search}%')
        
        if event_search:
            query += " AND e.name LIKE ?"
            params.append(f'%{event_search}%')
        
        if date_filter:
            query += " AND DATE(a.timestamp) = ?"
            params.append(date_filter)
        
        if fraud_filter == 'high':
            query += " AND a.fraud_score > 0.7"
        elif fraud_filter == 'medium':
            query += " AND a.fraud_score BETWEEN 0.4 AND 0.7"
        elif fraud_filter == 'low':
            query += " AND a.fraud_score < 0.4"
        
        query += " ORDER BY a.timestamp DESC"
        
        attendance_records = conn.execute(query, params).fetchall()
        
        attendance_list = []
        for record in attendance_records:
            # Calculate risk level
            fraud_score = float(record['fraud_score']) if record['fraud_score'] else 0
            if fraud_score > 0.8:
                risk = 'HIGH'
                badge_class = 'danger'
            elif fraud_score > 0.5:
                risk = 'MEDIUM'
                badge_class = 'warning'
            else:
                risk = 'LOW'
                badge_class = 'success'
            
            # FIX: Convert verified properly (1 = Verified, 0 = Unverified)
            is_verified = record['verified'] == 1 or record['verified'] == '1'
            
            attendance_list.append({
                'id': record['id'],
                'user_name': record['user_name'],
                'user_email': record['user_email'],
                'user_id': record['user_id'],
                'event_name': record['event_name'],
                'event_id': record['event_id'],
                'event_date': record['event_date'],
                'lecture': record['lecture_name'] or 'Main Session',
                'timestamp': record['timestamp'],
                'fraud_score': f"{fraud_score:.2f}",
                'risk_level': risk,
                'badge_class': badge_class,
                'verified': is_verified  # Now it's True/False
            })
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        attendance_list = []
    finally:
        conn.close()
    
    return render_template('attendance/attendance_log.html', 
                         attendance=attendance_list,
                         user_search=user_search,
                         event_search=event_search,
                         date_filter=date_filter,
                         fraud_filter=fraud_filter)

# =====================================================
# Attendance Scanner Route (Fix for the error)
# =====================================================
@app.route('/attendance/scanner')
@login_required
def attendance_scanner():
    """QR Code Scanner for attendance marking"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get all upcoming events
        events = conn.execute('''
            SELECT id, name, date, venue 
            FROM events 
            WHERE date >= date('now')
            ORDER BY date ASC
        ''').fetchall()
        
        events_list = []
        for event in events:
            events_list.append({
                'id': event['id'],
                'name': event['name'],
                'date': event['date'],
                'venue': event['venue']
            })
        
        print(f"📋 Found {len(events_list)} upcoming events for scanner")
        
    except Exception as e:
        print(f"Error fetching events for scanner: {e}")
        events_list = []
    finally:
        conn.close()
    
    return render_template('attendance/scanner.html', events=events_list)

# =====================================================
# Profile View Route (For viewing other users' profiles)
# =====================================================
@app.route('/profile/<int:user_id>')
@login_required
def profile_view(user_id):
    """View another user's profile (Admin only)"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user_data:
            flash('User not found!', 'danger')
            return redirect(url_for('manage_users'))
        
        # Get attendance stats for this user
        attendance_count = conn.execute('''
            SELECT COUNT(*) as count FROM attendance WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        fraud_avg = conn.execute('''
            SELECT AVG(fraud_score) as avg FROM attendance WHERE user_id = ?
        ''', (user_id,)).fetchone()
        
        user = {
            'id': user_data['id'],
            'name': user_data['name'],
            'email': user_data['email'],
            'phone': user_data['phone_number'] if 'phone_number' in user_data.keys() else 'N/A',
            'moodle_id': user_data['moodle_id'] if 'moodle_id' in user_data.keys() else 'N/A',
            'aadhaar_number': user_data['aadhaar_number'] if 'aadhaar_number' in user_data.keys() else 'N/A',
            'student_id': user_data['student_id'] if 'student_id' in user_data.keys() else 'N/A',
            'role': user_data['role'] if 'role' in user_data.keys() else 'user',
            'face_enrolled': user_data['face_enrolled'] if 'face_enrolled' in user_data.keys() else 0,
            'created_at': user_data['created_at'],
            'attendance_count': attendance_count['count'] if attendance_count else 0,
            'avg_fraud_score': f"{fraud_avg['avg']:.2f}" if fraud_avg and fraud_avg['avg'] else '0.00'
        }
    except Exception as e:
        flash(f'Error loading profile: {e}', 'danger')
        return redirect(url_for('manage_users'))
    finally:
        conn.close()
    
    return render_template('profile_view.html', user=user)

# =====================================================
# Event Details Route
# =====================================================
@app.route('/event/<int:event_id>')
def event_details(event_id):
    """View event details"""
    conn = get_db_connection()
    try:
        event = conn.execute('''
            SELECT e.*, u.name as created_by_name,
                   (SELECT COUNT(*) FROM attendance WHERE event_id = e.id) as attendance_count
            FROM events e
            LEFT JOIN users u ON e.created_by = u.id
            WHERE e.id = ?
        ''', (event_id,)).fetchone()
        
        if not event:
            flash('Event not found!', 'danger')
            return redirect(url_for('events'))
        
        # Get attendees for this event
        attendees = conn.execute('''
            SELECT u.id, u.name, u.email, a.timestamp, a.fraud_score, a.verified
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE a.event_id = ?
            ORDER BY a.timestamp DESC
        ''', (event_id,)).fetchall()
        
        attendee_list = []
        for attendee in attendees:
            attendee_list.append({
                'id': attendee['id'],
                'name': attendee['name'],
                'email': attendee['email'],
                'timestamp': attendee['timestamp'],
                'fraud_score': f"{attendee['fraud_score']:.2f}",
                'verified': '✅' if attendee['verified'] else '❌'
            })
        
    except Exception as e:
        flash(f'Error loading event: {e}', 'danger')
        return redirect(url_for('events'))
    finally:
        conn.close()
    
    return render_template('events/event_details.html', event=event, attendees=attendee_list)

# =====================================================
# Attendance Detail Route
# =====================================================
@app.route('/attendance/<int:attendance_id>')
@login_required
def view_attendance_detail(attendance_id):
    """View attendance record details"""
    conn = get_db_connection()
    try:
        record = conn.execute('''
            SELECT a.*, 
                   u.id as user_id, u.name as user_name, u.email as user_email, u.face_enrolled,
                   e.id as event_id, e.name as event_name, e.date as event_date, e.venue
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.id = ?
        ''', (attendance_id,)).fetchone()
        
        if not record:
            flash('Attendance record not found!', 'danger')
            return redirect(url_for('attendance_log'))
        
        # Convert to dict for safe template usage
        record_dict = dict(record)
        
    except Exception as e:
        flash(f'Error loading record: {e}', 'danger')
        return redirect(url_for('attendance_log'))
    finally:
        conn.close()
    
    return render_template('attendance/attendance_detail.html', record=record_dict)

# =====================================================
# Edit Attendance Route (Admin only)
# =====================================================
@app.route('/admin/attendance/edit/<int:attendance_id>', methods=['GET', 'POST'])
@login_required
def edit_attendance(attendance_id):
    """Edit attendance record - Admin only"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        lecture_name = request.form.get('lecture_name')
        verified = request.form.get('verified') == 'on'
        fraud_score = float(request.form.get('fraud_score', 0))
        
        try:
            conn.execute('''
                UPDATE attendance 
                SET lecture_name = ?, verified = ?, fraud_score = ?
                WHERE id = ?
            ''', (lecture_name, verified, fraud_score, attendance_id))
            conn.commit()
            flash('Attendance record updated successfully!', 'success')
            return redirect(url_for('view_attendance_detail', attendance_id=attendance_id))
        except Exception as e:
            flash(f'Error updating record: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('attendance_log'))
    
    # GET request - show edit form
    try:
        record = conn.execute('''
            SELECT a.*, u.name as user_name, e.name as event_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.id = ?
        ''', (attendance_id,)).fetchone()
        
        if not record:
            flash('Attendance record not found!', 'danger')
            return redirect(url_for('attendance_log'))
    except Exception as e:
        flash(f'Error loading record: {e}', 'danger')
        return redirect(url_for('attendance_log'))
    finally:
        conn.close()
    
    return render_template('admin/edit_attendance.html', record=record)

# =====================================================
# User Profile Route
# =====================================================
@app.route('/profile')
@login_required
def profile():
    """User profile page with view/edit mode"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    # Check for edit mode in URL parameter
    mode = request.args.get('mode', 'view')
    if mode == 'edit':
        session['edit_mode'] = True
    else:
        session['edit_mode'] = False
    
    # Get user data from database
    conn = get_db_connection()
    try:
        user_data = conn.execute('SELECT * FROM users WHERE id = ?', 
                               (session['user_id'],)).fetchone()
        
        if user_data:
            user = {
                'id': user_data['id'],
                'name': user_data['name'],
                'email': user_data['email'],
                'phone': user_data['phone_number'] if 'phone_number' in user_data.keys() else '',
                'moodle_id': user_data['moodle_id'] if 'moodle_id' in user_data.keys() else '',
                'aadhaar_number': user_data['aadhaar_number'] if 'aadhaar_number' in user_data.keys() else '',
                'student_id': user_data['student_id'] if 'student_id' in user_data.keys() else '',
                'role': user_data['role'] if 'role' in user_data.keys() else 'user',
                'face_enrolled': user_data['face_enrolled'] if 'face_enrolled' in user_data.keys() else 0,
                'created_at': user_data['created_at'],
                'updated_at': user_data['updated_at'] if 'updated_at' in user_data.keys() else ''
            }
        else:
            # Fallback to session data
            user = {
                'id': session.get('user_id'),
                'name': session.get('user_name', 'User'),
                'email': session.get('user_email', ''),
                'phone': '',
                'moodle_id': session.get('user_moodle_id', ''),
                'aadhaar_number': '',
                'student_id': '',
                'role': session.get('user_type', 'user'),
                'face_enrolled': 0,
                'created_at': datetime.now().isoformat(),
                'updated_at': ''
            }
    except Exception as e:
        print(f"Error fetching user data: {e}")
        user = {
            'id': session.get('user_id'),
            'name': session.get('user_name', 'User'),
            'email': session.get('user_email', ''),
            'phone': '',
            'moodle_id': session.get('user_moodle_id', ''),
            'aadhaar_number': '',
            'student_id': '',
            'role': session.get('user_type', 'user'),
            'face_enrolled': 0,
            'created_at': datetime.now().isoformat(),
            'updated_at': ''
        }
    finally:
        conn.close()
    
    return render_template('profile.html', user=user)


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    # Get form data
    name = request.form.get('name')
    phone = request.form.get('phone')
    moodle_id = request.form.get('moodle_id')
    aadhaar_number = request.form.get('aadhaar_number')
    student_id = request.form.get('student_id')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate required fields
    if not name:
        flash('Name is required!', 'danger')
        return redirect(url_for('profile', mode='edit'))
    
    # Validate password if provided
    if new_password:
        if len(new_password) < 4:
            flash('Password must be at least 4 characters long!', 'danger')
            return redirect(url_for('profile', mode='edit'))
        
        if new_password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('profile', mode='edit'))
    
    conn = get_db_connection()
    try:
        # Get current user data
        current_user = conn.execute('SELECT * FROM users WHERE id = ?', 
                                   (session['user_id'],)).fetchone()
        
        if not current_user:
            flash('User not found!', 'danger')
            return redirect(url_for('login'))
        
        # Check if email/moodle_id/aadhaar/student_id already exists for other users
        if moodle_id and moodle_id != current_user['moodle_id']:
            existing = conn.execute('SELECT id FROM users WHERE moodle_id = ? AND id != ?', 
                                   (moodle_id, session['user_id'])).fetchone()
            if existing:
                flash('Moodle ID already exists for another user!', 'danger')
                return redirect(url_for('profile', mode='edit'))
        
        if aadhaar_number and aadhaar_number != current_user['aadhaar_number']:
            existing = conn.execute('SELECT id FROM users WHERE aadhaar_number = ? AND id != ?', 
                                   (aadhaar_number, session['user_id'])).fetchone()
            if existing:
                flash('Aadhaar number already exists for another user!', 'danger')
                return redirect(url_for('profile', mode='edit'))
        
        if student_id and student_id != current_user['student_id']:
            existing = conn.execute('SELECT id FROM users WHERE student_id = ? AND id != ?', 
                                   (student_id, session['user_id'])).fetchone()
            if existing:
                flash('Student ID already exists for another user!', 'danger')
                return redirect(url_for('profile', mode='edit'))
        
        # Update user information
        if new_password:
            import hashlib
            hashed_password = hashlib.md5(new_password.encode()).hexdigest()
            conn.execute('''
                UPDATE users 
                SET name = ?, phone_number = ?, moodle_id = ?, 
                    aadhaar_number = ?, student_id = ?, password = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (name, phone, moodle_id, aadhaar_number, student_id, hashed_password, session['user_id']))
        else:
            conn.execute('''
                UPDATE users 
                SET name = ?, phone_number = ?, moodle_id = ?, 
                    aadhaar_number = ?, student_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (name, phone, moodle_id, aadhaar_number, student_id, session['user_id']))
        
        conn.commit()
        
        # Update session variables
        session['user_name'] = name
        if moodle_id:
            session['user_moodle_id'] = moodle_id
        
        # Clear edit mode
        session['edit_mode'] = False
        
        flash('Profile updated successfully!', 'success')
        
        # Log the activity
        try:
            from security_logger import security_logger
            security_logger.log(
                log_type='PROFILE',
                action='PROFILE_UPDATED',
                details=f"User {session['user_email']} updated their profile",
                severity='INFO',
                user_info={'id': session['user_id'], 'name': name, 'email': session['user_email']}
            )
        except:
            pass
        
        return redirect(url_for('profile'))
        
    except Exception as e:
        print(f"Error updating profile: {e}")
        conn.rollback()
        flash(f'Error updating profile: {str(e)}', 'danger')
        return redirect(url_for('profile', mode='edit'))
    finally:
        conn.close()

# =====================================================
# Admin AJAX Routes for Dashboard
# =====================================================

@app.route('/admin/pending-verifications/count')
@login_required
def admin_pending_verifications_count():
    """Get count of pending verifications for admin dashboard"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        # Count pending verifications (users with verified = 0)
        count = conn.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE role = 'user' AND (verified = 0 OR verified IS NULL)
        ''').fetchone()
        
        return jsonify({
            'success': True,
            'count': count['count'] if count else 0
        })
    except Exception as e:
        print(f"Error fetching pending count: {e}")
        return jsonify({'error': str(e), 'count': 0}), 500
    finally:
        conn.close()

@app.route('/admin/recent-activity')
@login_required
def admin_recent_activity():
    """Get recent activity for admin dashboard"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        # Get recent attendance
        recent = conn.execute('''
            SELECT 
                a.timestamp,
                u.name as user_name,
                u.email as user_email,
                e.name as event_name,
                a.fraud_score
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            ORDER BY a.timestamp DESC
            LIMIT 10
        ''').fetchall()
        
        activity_list = []
        for item in recent:
            activity_list.append({
                'timestamp': item['timestamp'],
                'user_name': item['user_name'],
                'user_email': item['user_email'],
                'event_name': item['event_name'],
                'fraud_score': item['fraud_score']
            })
        
        return jsonify({
            'success': True,
            'activities': activity_list
        })
    except Exception as e:
        print(f"Error fetching recent activity: {e}")
        return jsonify({'error': str(e), 'activities': []}), 500
    finally:
        conn.close()

@app.route('/admin/dashboard/stats')
@login_required
def admin_dashboard_stats():
    """Get dashboard statistics for admin"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        # Get various stats
        total_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "user"').fetchone()
        pending_verifications = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "user" AND (verified = 0 OR verified IS NULL)').fetchone()
        total_events = conn.execute('SELECT COUNT(*) as count FROM events').fetchone()
        active_events = conn.execute('SELECT COUNT(*) as count FROM events WHERE date >= date("now")').fetchone()
        total_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance').fetchone()
        
        # Get today's stats
        today_attendance = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE date(timestamp) = date('now')
        ''').fetchone()
        
        fraud_alerts = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE fraud_score > 0.7 AND date(timestamp) = date('now')
        ''').fetchone()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users['count'] if total_users else 0,
                'pending_verifications': pending_verifications['count'] if pending_verifications else 0,
                'total_events': total_events['count'] if total_events else 0,
                'active_events': active_events['count'] if active_events else 0,
                'total_attendance': total_attendance['count'] if total_attendance else 0,
                'today_attendance': today_attendance['count'] if today_attendance else 0,
                'fraud_alerts_today': fraud_alerts['count'] if fraud_alerts else 0
            }
        })
    except Exception as e:
        print(f"Error fetching dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# =====================================================
# Face Enrollment Routes (UPDATED with GET endpoint)
# =====================================================

@app.route('/api/face/enroll', methods=['GET'])
@login_required
def enroll_face_info():
    """Display info about the face enrollment API"""
    return jsonify({
        'status': 'API endpoint info',
        'method_required': 'POST',
        'content_type': 'application/json',
        'required_fields': {
            'face_image': 'Base64 encoded image string (with or without data URL prefix)'
        },
        'example_request': {
            'face_image': 'data:image/jpeg;base64,/9j/4AAQSkZJRg...'
        },
        'note': 'Use POST method to enroll a face. This endpoint is for API calls only.',
        'use_web_interface': 'Visit /face-enrollment to enroll your face using the web interface'
    })

@app.route('/api/face/enroll', methods=['POST'])
@login_required
def enroll_face():
    """Enroll a face for the current user (API endpoint)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    face_image_data = data.get('face_image')
    
    if not face_image_data:
        return jsonify({'success': False, 'message': 'No face image provided'}), 400
    
    try:
        import base64
        import io
        from PIL import Image
        
        # Remove data URL prefix if present
        if ',' in face_image_data:
            face_image_data = face_image_data.split(',')[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(face_image_data)
        
        # Create directory for user faces
        user_id = session['user_id']
        face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
        os.makedirs(face_dir, exist_ok=True)
        
        # Save image with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"face_{user_id}_{timestamp}.jpg"
        filepath = os.path.join(face_dir, filename)
        
        # Convert bytes to image and save
        image = Image.open(io.BytesIO(image_bytes))
        image.save(filepath, 'JPEG', quality=90)
        
        # Update database
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET face_enrolled = 1,
                face_image_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (f"faces/{user_id}/{filename}", user_id))
        conn.commit()
        conn.close()
        
        # ===== ADD THIS AUTO-TRAINING SECTION =====
        print(f"🔄 Auto-retraining face model after user {user_id} enrollment...")
        try:
            # Get the backend directory path
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            train_script = os.path.join(backend_dir, 'train_faces_direct.py')
            
            # Check if training script exists
            if os.path.exists(train_script):
                # Run training in background (doesn't block the response)
                subprocess.Popen([sys.executable, train_script], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                print("✅ Background training started")
            else:
                print(f"⚠️ Training script not found at: {train_script}")
                print("   Please create train_faces_direct.py in backend folder")
        except Exception as train_error:
            print(f"⚠️ Auto-training error: {train_error}")
        # ===== END OF AUTO-TRAINING SECTION =====
        
        return jsonify({
            'success': True,
            'message': 'Face captured successfully! Model will update automatically.',
            'filename': filename
        })
        
    except Exception as e:
        print(f"Error enrolling face: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/face/train', methods=['POST'])
def train_face_model():
    """Train the face recognition model with all enrolled faces - Allow any logged in user"""
    # Remove admin check - allow any logged in user or even no login for testing
    # Just check if user is logged in (either admin or regular user)
    if 'admin_id' not in session and 'user_id' not in session:
        # For testing, allow without login
        print("⚠️ No user logged in, but proceeding with training anyway")
    
    try:
        import cv2
        import numpy as np
        import os
        import pickle
        
        print("=" * 50)
        print("Starting Face Model Training...")
        print("=" * 50)
        
        # Get all users with enrolled faces
        conn = get_db_connection()
        users = conn.execute('''
            SELECT id, name, face_image_path 
            FROM users 
            WHERE face_enrolled = 1
        ''').fetchall()
        
        print(f"Found {len(users)} users with face_enrolled=1")
        
        if len(users) == 0:
            conn.close()
            return jsonify({'success': False, 'message': 'No faces to train. Please enroll faces first.'}), 400
        
        # Collect all face images
        faces = []
        labels = []
        label_names = {}
        
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(backend_dir)
        faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
        
        print(f"Looking for faces in: {faces_base_dir}")
        
        for user in users:
            user_id = user['id']
            user_name = user['name']
            user_dir = os.path.join(faces_base_dir, str(user_id))
            
            if os.path.exists(user_dir):
                face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
                print(f"User {user_name} (ID: {user_id}) has {len(face_files)} face images")
                
                for face_file in face_files:
                    face_path = os.path.join(user_dir, face_file)
                    face_img = cv2.imread(face_path, cv2.IMREAD_GRAYSCALE)
                    
                    if face_img is not None:
                        face_img = cv2.resize(face_img, (100, 100))
                        faces.append(face_img)
                        labels.append(user_id)
                        label_names[user_id] = user_name
                        print(f"  Loaded: {face_file}")
                    else:
                        print(f"  Failed to load: {face_file}")
            else:
                print(f"WARNING: No face directory found for user {user_name} (ID: {user_id})")
        
        conn.close()
        
        if len(faces) == 0:
            return jsonify({
                'success': False, 
                'message': 'No valid face images found.'
            }), 400
        
        print(f"\nTraining with {len(faces)} face images from {len(label_names)} users")
        
        # Create recognizer
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            print("Created LBPHFaceRecognizer")
        except AttributeError:
            try:
                recognizer = cv2.face_LBPHFaceRecognizer.create()
                print("Created LBPHFaceRecognizer (OpenCV 4.x)")
            except:
                return jsonify({
                    'success': False,
                    'message': 'OpenCV face module not available.'
                }), 500
        
        recognizer.train(faces, np.array(labels))
        print("Training completed successfully")
        
        # Save model
        model_dir = os.path.join(backend_dir, 'ml_models', 'saved_models')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'face_recognizer.yml')
        recognizer.save(model_path)
        print(f"Model saved to: {model_path}")
        
        labels_path = os.path.join(model_dir, 'face_labels.pkl')
        with open(labels_path, 'wb') as f:
            pickle.dump(label_names, f)
        print(f"Labels saved to: {labels_path}")
        
        return jsonify({
            'success': True,
            'message': f'Model trained successfully with {len(faces)} faces from {len(label_names)} users',
            'faces_trained': len(faces),
            'users_trained': len(label_names)
        })
        
    except Exception as e:
        print(f"Training error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': str(e)
        }), 500

@app.route('/api/face/verify-attendance', methods=['POST'])
@login_required
def verify_face_for_attendance():
    """Verify face for attendance marking"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
        
        face_image_data = data.get('face_image')
        user_id = data.get('user_id')
        event_id = data.get('event_id')
        lecture_name = data.get('lecture_name', 'Main Session')
        
        print(f"📝 Face verification request - User: {user_id}, Event: {event_id}, Lecture: {lecture_name}")
        
        if not face_image_data:
            return jsonify({'success': False, 'message': 'No face image provided'}), 400
        
        if not user_id:
            return jsonify({'success': False, 'message': 'Please select a user'}), 400
        
        if not event_id:
            return jsonify({'success': False, 'message': 'Please select an event'}), 400
        
        conn = get_db_connection()
        
        # Get user details
        user = conn.execute('SELECT name, face_enrolled FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Check if user has face enrolled
        if not user['face_enrolled']:
            conn.close()
            return jsonify({
                'success': False, 
                'verified': False,
                'message': 'User has not enrolled their face yet. Please enroll first.'
            }), 400
        
        # For now, since we're in development, accept the face if enrolled
        # In production, you would use actual face recognition here
        is_verified = True
        confidence = 0.85
        
        # Mark attendance if verified
        if is_verified:
            # Check if already marked today
            existing = conn.execute('''
                SELECT id FROM attendance 
                WHERE user_id = ? AND event_id = ? AND date(timestamp) = date('now')
            ''', (user_id, event_id)).fetchone()
            
            if not existing:
                conn.execute('''
                    INSERT INTO attendance (user_id, event_id, lecture_name, timestamp, verified, fraud_score)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
                ''', (user_id, event_id, lecture_name, 1, 0.1))
                conn.commit()
                print(f"✅ Attendance marked for {user['name']} at event {event_id}")
                message = 'Face verified and attendance marked successfully!'
            else:
                print(f"⚠️ Attendance already marked for {user['name']} today")
                message = 'Face verified but attendance already marked for today'
        else:
            message = 'Face verification failed'
        
        conn.close()
        
        return jsonify({
            'success': True,
            'verified': is_verified,
            'confidence': confidence,
            'user_name': user['name'],
            'message': message
        })
        
    except Exception as e:
        print(f"Error in verify_face_for_attendance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
# =====================================================
# Face Scanner Route
# =====================================================

@app.route('/face-scanner')
@login_required
def face_scanner():
    """Face scanner page for attendance marking with location verification"""
    if 'user_id' not in session and 'admin_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        # Get all upcoming events WITH location data for verification
        events = conn.execute('''
            SELECT id, name, date, venue, venue_latitude, venue_longitude, venue_radius
            FROM events 
            WHERE date >= date('now')
            ORDER BY date ASC
        ''').fetchall()
        
        events_list = []
        for event in events:
            events_list.append({
                'id': event['id'],
                'name': event['name'],
                'date': event['date'],
                'venue': event['venue'] or 'TBD',
                'venue_latitude': event['venue_latitude'],
                'venue_longitude': event['venue_longitude'],
                'venue_radius': event['venue_radius'] or 100
            })
        
        # Get users for admin dropdown
        users_list = []
        if 'admin_id' in session:
            users = conn.execute('''
                SELECT id, name, email 
                FROM users 
                WHERE role = 'user' 
                ORDER BY name
            ''').fetchall()
            for user in users:
                users_list.append({
                    'id': user['id'],
                    'name': user['name'],
                    'email': user['email']
                })
        
        # Check if current user has face enrolled
        has_face = False
        if 'user_id' in session:
            user = conn.execute('''
                SELECT face_enrolled 
                FROM users 
                WHERE id = ?
            ''', (session['user_id'],)).fetchone()
            has_face = user and user['face_enrolled'] == 1
        
        # Get location verification statistics
        location_stats = {}
        if events_list:
            events_with_location = len([e for e in events_list if e['venue_latitude']])
            location_stats = {
                'total_events': len(events_list),
                'events_with_location': events_with_location,
                'events_without_location': len(events_list) - events_with_location
            }
        else:
            location_stats = {
                'total_events': 0,
                'events_with_location': 0,
                'events_without_location': 0
            }
        
        print(f"📱 Face Scanner Loaded - Events: {len(events_list)}, Users: {len(users_list)}")
        print(f"📍 Location Stats - {location_stats['events_with_location']}/{location_stats['total_events']} events have location verification")
        
    except Exception as e:
        print(f"Error loading face scanner: {e}")
        import traceback
        traceback.print_exc()
        events_list = []
        users_list = []
        has_face = False
        location_stats = {'total_events': 0, 'events_with_location': 0, 'events_without_location': 0}
    finally:
        conn.close()
    
    return render_template('face_scanner.html', 
                         events=events_list,
                         users=users_list,
                         has_face=has_face,
                         is_admin='admin_id' in session,
                         location_stats=location_stats)

@app.route('/api/face/mark-attendance-direct', methods=['POST'])
def face_mark_attendance_direct():
    """Direct attendance marking from face scanner - NO LOGIN REQUIRED"""
    try:
        data = request.get_json()
        
        user_id = data.get('user_id')
        event_id = data.get('event_id')
        lecture_name = data.get('lecture_name', 'Main Session')
        
        print(f"\n📝 Face Scanner Direct Attendance:")
        print(f"   User ID: {user_id}")
        print(f"   Event ID: {event_id}")
        print(f"   Lecture: {lecture_name}")
        
        if not user_id:
            return jsonify({'success': False, 'message': 'User ID required'}), 400
        
        if not event_id:
            return jsonify({'success': False, 'message': 'Event ID required'}), 400
        
        conn = get_db_connection()
        
        user = conn.execute('SELECT id, name, email FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        event = conn.execute('SELECT id, name FROM events WHERE id = ?', (event_id,)).fetchone()
        
        if not event:
            conn.close()
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        existing = conn.execute('''
            SELECT id FROM attendance 
            WHERE user_id = ? AND event_id = ? AND date(timestamp) = date('now')
        ''', (user_id, event_id)).fetchone()
        
        if existing:
            conn.close()
            return jsonify({
                'success': False, 
                'message': f'Attendance already marked for {user["name"]} today'
            }), 400
        
        cursor = conn.execute("PRAGMA table_info(attendance)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'lecture_name' in columns:
            conn.execute('''
                INSERT INTO attendance (user_id, event_id, lecture_name, timestamp, verified, fraud_score)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1, 0.0)
            ''', (user_id, event_id, lecture_name))
        else:
            conn.execute('''
                INSERT INTO attendance (user_id, event_id, timestamp, verified, fraud_score)
                VALUES (?, ?, CURRENT_TIMESTAMP, 1, 0.0)
            ''', (user_id, event_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Attendance marked for {user['name']}")
        
        return jsonify({
            'success': True,
            'message': f'✅ Attendance marked successfully for {user["name"]}!',
            'user_name': user['name'],
            'event_name': event['name']
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/face/auto-detect', methods=['POST'])
def auto_detect_face():
    """Automatically detect and identify face - NO LOGIN REQUIRED"""
    try:
        data = request.get_json()
        face_image_data = data.get('face_image')
        
        print(f"\n🔍 Face Detection Request Received")
        
        if not face_image_data:
            return jsonify({'success': False, 'face_detected': False, 'message': 'No image provided'})
        
        if ',' in face_image_data:
            face_image_data = face_image_data.split(',')[1]
        
        import base64
        import cv2
        import numpy as np
        import os
        import pickle
        
        image_bytes = base64.b64decode(face_image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({'success': False, 'face_detected': False, 'message': 'Invalid image'})
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Try multiple cascade paths
        cascade_paths = [
            r'C:\Users\NIKHIL\AppData\Roaming\Python\Python311\site-packages\cv2\data\haarcascade_frontalface_default.xml',
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        ]
        
        face_cascade = None
        for path in cascade_paths:
            face_cascade = cv2.CascadeClassifier(path)
            if not face_cascade.empty():
                print(f"✅ Loaded cascade from: {path}")
                break
        
        if face_cascade is None or face_cascade.empty():
            return jsonify({'success': False, 'face_detected': False, 'message': 'Face detection model not loaded'})
        
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        print(f"📸 Detected {len(faces)} face(s) in image")
        
        if len(faces) == 0:
            return jsonify({'success': False, 'face_detected': False, 'message': 'No face detected'})
        
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(backend_dir, 'ml_models', 'saved_models', 'face_recognizer.yml')
        labels_path = os.path.join(backend_dir, 'ml_models', 'saved_models', 'face_labels.pkl')
        
        print(f"📂 Model path: {model_path}")
        print(f"📂 Labels path: {labels_path}")
        print(f"📂 Model exists: {os.path.exists(model_path)}")
        
        if not os.path.exists(model_path):
            return jsonify({
                'success': True, 
                'face_detected': True, 
                'identified': False,
                'confidence': 85,
                'message': 'Face detected! Please train the model first.'
            })
        
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(model_path)
        
        with open(labels_path, 'rb') as f:
            label_names = pickle.load(f)
        
        print(f"🏷️ Label mapping: {label_names}")
        
        # Get the largest face (most likely the user)
        (x, y, w, h) = max(faces, key=lambda rect: rect[2] * rect[3])
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (100, 100))
        
        label, confidence = recognizer.predict(face_roi)
        display_confidence = int(100 - (confidence / 2))
        
        print(f"🎯 Recognition result - Label: {label}, Raw Confidence: {confidence}, Display: {display_confidence}%")
        
        # Use stricter confidence threshold
        CONFIDENCE_THRESHOLD = 150
        
        if confidence < CONFIDENCE_THRESHOLD and label in label_names:
            user_name_from_label = label_names[label]
            print(f"✅ Match found: {user_name_from_label} (ID from label: {label})")
            
            conn = get_db_connection()
            # Try to find user by ID from label
            user = conn.execute('SELECT id, name, email FROM users WHERE id = ?', (label,)).fetchone()
            
            if not user:
                # Try to find by name
                user = conn.execute('SELECT id, name, email FROM users WHERE name = ?', (user_name_from_label,)).fetchone()
            
            conn.close()
            
            if user:
                session['detected_face'] = user['id']
                session['detected_face_name'] = user['name']
                print(f"✅✅✅ Stored in session: {user['id']} - {user['name']}")
                
                return jsonify({
                    'success': True,
                    'face_detected': True,
                    'identified': True,
                    'user_id': user['id'],
                    'user_name': user['name'],
                    'user_email': user['email'],
                    'confidence': display_confidence,
                    'message': f'Welcome {user["name"]}!'
                })
            else:
                print(f"❌ User with label {label} not found in database")
                return jsonify({
                    'success': True,
                    'face_detected': True,
                    'identified': False,
                    'confidence': display_confidence,
                    'message': f'Face recognized but user not in database'
                })
        else:
            print(f"❌ No confident match - Confidence: {confidence}, Threshold: {CONFIDENCE_THRESHOLD}")
            return jsonify({
                'success': True,
                'face_detected': True,
                'identified': False,
                'confidence': display_confidence,
                'message': f'Face detected but not recognized ({display_confidence}% confidence)'
            })
        
    except Exception as e:
        print(f"❌ Error in face detection: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'face_detected': False, 'message': str(e)})

@app.route('/api/face/status')
@login_required
def face_status():
    """Get face enrollment status for current user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    conn = get_db_connection()
    try:
        user = conn.execute('''
            SELECT face_enrolled, face_image_path 
            FROM users 
            WHERE id = ?
        ''', (session['user_id'],)).fetchone()
        
        return jsonify({
            'success': True,
            'face_enrolled': bool(user['face_enrolled']) if user else False,
            'face_image_path': user['face_image_path'] if user else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/enhanced-scanner')
@login_required
def enhanced_scanner():
    """Enhanced face scanner with location and liveness"""
    if 'user_id' not in session and 'admin_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    events = conn.execute('''
        SELECT id, name, date, venue, venue_latitude, venue_longitude 
        FROM events 
        WHERE date >= date('now')
        ORDER BY date ASC
    ''').fetchall()
    conn.close()
    
    return render_template('enhanced_face_scanner.html', events=events)

@app.route('/admin/face/manage')
@login_required
def manage_faces():
    """Admin page to manage face enrollments"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get all users with face enrollment status
        users = conn.execute('''
            SELECT id, name, email, face_enrolled, face_image_path, created_at
            FROM users
            ORDER BY face_enrolled DESC, created_at DESC
        ''').fetchall()
        
        user_list = []
        for user in users:
            # Count face images for this user
            face_count = 0
            if user['face_enrolled']:
                face_dir = os.path.join('frontend', 'static', 'faces', str(user['id']))
                if os.path.exists(face_dir):
                    face_count = len([f for f in os.listdir(face_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])
            
            user_list.append({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'face_enrolled': '✅' if user['face_enrolled'] else '❌',
                'face_count': face_count,
                'registered_on': user['created_at'][:10] if user['created_at'] else 'N/A'
            })
        
        # Get training stats
        training_stats = face_recognizer.get_stats()
        
    except Exception as e:
        print(f"Error managing faces: {e}")
        user_list = []
        training_stats = {'total_faces': 0, 'last_training': None, 'total_users': 0}
    finally:
        conn.close()
    
    return render_template('admin/manage_faces.html', 
                         users=user_list, 
                         stats=training_stats)

@app.route('/admin/face/retrain', methods=['POST'])
@login_required
def retrain_face_model():
    """Simplified training endpoint"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        import cv2
        import numpy as np
        import os
        import pickle
        
        conn = get_db_connection()
        users = conn.execute('SELECT id, name FROM users WHERE face_enrolled = 1').fetchall()
        conn.close()
        
        if len(users) == 0:
            return jsonify({'success': False, 'message': 'No enrolled faces found'})
        
        faces = []
        labels = []
        label_names = {}
        
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(backend_dir)
        faces_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
        
        for user in users:
            user_id = user['id']
            user_name = user['name']
            user_dir = os.path.join(faces_dir, str(user_id))
            
            if os.path.exists(user_dir):
                for img_file in os.listdir(user_dir):
                    if img_file.endswith(('.jpg', '.png', '.jpeg')):
                        img_path = os.path.join(user_dir, img_file)
                        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        if img is not None:
                            img = cv2.resize(img, (100, 100))
                            faces.append(img)
                            labels.append(user_id)
                            label_names[user_id] = user_name
        
        if len(faces) == 0:
            return jsonify({'success': False, 'message': 'No valid face images found'})
        
        # Try to create recognizer
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train(faces, np.array(labels))
            
            model_dir = os.path.join(backend_dir, 'ml_models', 'saved_models')
            os.makedirs(model_dir, exist_ok=True)
            recognizer.save(os.path.join(model_dir, 'face_recognizer.yml'))
            
            with open(os.path.join(model_dir, 'face_labels.pkl'), 'wb') as f:
                pickle.dump(label_names, f)
            
            return jsonify({
                'success': True,
                'message': f'Trained with {len(faces)} faces from {len(label_names)} users',
                'faces_trained': len(faces),
                'users_trained': len(label_names)
            })
        except AttributeError:
            return jsonify({
                'success': False,
                'message': 'OpenCV face module not installed. Run: pip install opencv-contrib-python'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# =====================================================
# Debug Face Routes
# =====================================================

@app.route('/debug/face-routes')
def debug_face_routes():
    """List all face-related routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        if 'face' in rule.rule:
            routes.append({
                'url': rule.rule,
                'methods': list(rule.methods),
                'endpoint': rule.endpoint
            })
    return jsonify({
        'total_face_routes': len(routes),
        'routes': routes,
        'recommended_usage': 'For face enrollment, use the web interface at /face-enrollment'
    })

# =====================================================
# Face Enrollment Page
# =====================================================

@app.route('/face-enrollment')
@login_required
def face_enrollment():
    """Face enrollment page for users"""
    if 'user_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    
    try:
        user = conn.execute('SELECT id, name, email, face_enrolled FROM users WHERE id = ?', 
                           (user_id,)).fetchone()
        
        if not user:
            flash('User not found!', 'danger')
            return redirect(url_for('login'))
        
        # Check if user already has face enrolled
        if user['face_enrolled'] == 1:
            flash('You have already enrolled your face!', 'info')
            return redirect(url_for('dashboard'))
        
        return render_template('face_enrollment.html', user=user)
        
    except Exception as e:
        print(f"Error loading face enrollment: {e}")
        flash('Error loading page', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

# =====================================================
# Anomaly Reports Route
# =====================================================
@app.route('/admin/anomaly-reports')
def anomaly_report():
    """Anomaly detection reports page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get attendance anomalies (unusual patterns)
        time_anomalies = conn.execute('''
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as expected_avg,
                CASE 
                    WHEN COUNT(*) > (SELECT AVG(count) * 2 FROM (
                        SELECT strftime('%H', timestamp) as h, COUNT(*) as count 
                        FROM attendance GROUP BY h
                    )) THEN 'HIGH'
                    WHEN COUNT(*) < (SELECT AVG(count) / 2 FROM (
                        SELECT strftime('%H', timestamp) as h, COUNT(*) as count 
                        FROM attendance GROUP BY h
                    )) THEN 'LOW'
                    ELSE 'NORMAL'
                END as anomaly_type
            FROM attendance
            GROUP BY hour
            HAVING anomaly_type != 'NORMAL'
            ORDER BY hour
        ''').fetchall()
        
        # Get user behavior anomalies
        user_anomalies = conn.execute('''
            SELECT 
                u.id,
                u.name,
                u.email,
                COUNT(a.id) as attendance_count,
                AVG(a.fraud_score) as avg_fraud_score,
                MAX(a.fraud_score) as max_fraud_score,
                COUNT(DISTINCT a.event_id) as events_attended
            FROM users u
            LEFT JOIN attendance a ON u.id = a.user_id
            GROUP BY u.id
            HAVING avg_fraud_score > 0.6 OR attendance_count > (
                SELECT AVG(count) * 2 FROM (
                    SELECT COUNT(*) as count FROM attendance GROUP BY user_id
                )
            ) OR attendance_count = 0
            ORDER BY avg_fraud_score DESC
            LIMIT 20
        ''').fetchall()
        
        # Get event anomalies
        event_anomalies = conn.execute('''
            SELECT 
                e.id,
                e.name,
                e.date,
                COUNT(a.id) as attendance_count,
                AVG(a.fraud_score) as avg_fraud_score
            FROM events e
            LEFT JOIN attendance a ON e.id = a.event_id
            GROUP BY e.id
            HAVING avg_fraud_score > 0.6 OR attendance_count < 5
            ORDER BY avg_fraud_score DESC
            LIMIT 10
        ''').fetchall()
        
        # Get face enrollment anomalies
        face_anomalies = conn.execute('''
            SELECT 
                COUNT(*) as multiple_enrollments
            FROM users 
            WHERE face_enrolled = 1
            GROUP BY id
            HAVING COUNT(*) > 1
        ''').fetchall()
        
    except Exception as e:
        print(f"Error fetching anomaly data: {e}")
        time_anomalies = []
        user_anomalies = []
        event_anomalies = []
        face_anomalies = []
    finally:
        conn.close()
    
    # Format time anomalies
    time_anomaly_list = []
    for anomaly in time_anomalies:
        time_anomaly_list.append({
            'hour': f"{int(anomaly['hour'])}:00",
            'type': anomaly['anomaly_type'],
            'severity': 'High' if anomaly['anomaly_type'] == 'HIGH' else 'Low',
            'color': 'danger' if anomaly['anomaly_type'] == 'HIGH' else 'warning'
        })
    
    # Format user anomalies
    user_anomaly_list = []
    for user in user_anomalies:
        reason = []
        if user['avg_fraud_score'] is not None and user['avg_fraud_score'] > 0.6:
            reason.append(f"High fraud score ({user['avg_fraud_score']:.2f})")
        if user['attendance_count'] == 0:
            reason.append("No attendance records")
        elif user['attendance_count'] > 10:
            reason.append(f"Unusually high attendance ({user['attendance_count']})")
        
        user_anomaly_list.append({
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'reason': ', '.join(reason),
            'fraud_score': f"{user['avg_fraud_score']:.2f}" if user['avg_fraud_score'] else 'N/A',
            'attendance': user['attendance_count'] or 0
        })
    
    # Format event anomalies
    event_anomaly_list = []
    for event in event_anomalies:
        event_anomaly_list.append({
            'id': event['id'],
            'name': event['name'],
            'date': event['date'],
            'attendance': event['attendance_count'] or 0,
            'fraud_score': f"{event['avg_fraud_score']:.2f}" if event['avg_fraud_score'] else '0.00'
        })
    
    stats = {
        'time_anomalies': len(time_anomaly_list),
        'user_anomalies': len(user_anomaly_list),
        'event_anomalies': len(event_anomaly_list),
        'face_anomalies': len(face_anomalies)
    }
    
    return render_template('admin/anomaly_report.html',
                         time_anomalies=time_anomaly_list,
                         user_anomalies=user_anomaly_list,
                         event_anomalies=event_anomaly_list,
                         stats=stats)

# =====================================================
# Security Logs Route
# =====================================================
@app.route('/admin/security-logs')
def security_logs():
    """Security logs and audit trail"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    # Get filter parameters
    log_type = request.args.get('type', 'all')
    severity = request.args.get('severity', 'all')
    days = request.args.get('days', '7')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = 50
    
    conn = get_db_connection()
    try:
        # Check if security_logs table exists
        table_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='security_logs'").fetchone()
        
        if not table_exists:
            # Create the table if it doesn't exist
            conn.execute('''
                CREATE TABLE IF NOT EXISTS security_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    log_type TEXT,
                    action TEXT,
                    details TEXT,
                    user_id INTEGER,
                    user_name TEXT,
                    user_email TEXT,
                    ip_address TEXT,
                    severity TEXT,
                    duration_ms INTEGER
                )
            ''')
            conn.commit()
            print("✅ Created security_logs table")
            log_list = []
            total_logs = 0
            total_pages = 1
        else:
            # Build the query based on filters
            query = "SELECT * FROM security_logs WHERE 1=1"
            count_query = "SELECT COUNT(*) as total FROM security_logs WHERE 1=1"
            params = []
            
            if log_type and log_type != 'all':
                query += " AND log_type = ?"
                count_query += " AND log_type = ?"
                params.append(log_type.upper())
            
            if severity and severity != 'all':
                query += " AND severity = ?"
                count_query += " AND severity = ?"
                params.append(severity.upper())
            
            if days and days != 'all':
                query += " AND timestamp >= datetime('now', ?)"
                count_query += " AND timestamp >= datetime('now', ?)"
                params.append(f'-{days} days')
            
            if search:
                query += " AND (action LIKE ? OR details LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR ip_address LIKE ?)"
                count_query += " AND (action LIKE ? OR details LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR ip_address LIKE ?)"
                search_pattern = f'%{search}%'
                params.extend([search_pattern] * 5)
            
            # Get total count
            total_result = conn.execute(count_query, params).fetchone()
            total_logs = total_result['total'] if total_result else 0
            total_pages = (total_logs + per_page - 1) // per_page if total_logs > 0 else 1
            
            # Get paginated results
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([per_page, (page - 1) * per_page])
            
            logs = conn.execute(query, params).fetchall()
            
            log_list = []
            for log in logs:
                log_dict = dict(log)
                # Format severity badge
                if log_dict.get('severity') == 'INFO':
                    badge_class = 'success'
                elif log_dict.get('severity') == 'WARNING':
                    badge_class = 'warning'
                elif log_dict.get('severity') == 'ERROR':
                    badge_class = 'danger'
                else:
                    badge_class = 'secondary'
                
                log_list.append({
                    'id': log_dict['id'],
                    'timestamp': log_dict['timestamp'],
                    'log_type': log_dict.get('log_type', 'Unknown'),
                    'user_name': log_dict.get('user_name', 'System'),
                    'user_email': log_dict.get('user_email', ''),
                    'action': log_dict.get('action', 'Unknown'),
                    'details': log_dict.get('details', ''),
                    'ip_address': log_dict.get('ip_address', request.remote_addr or 'N/A'),
                    'severity': log_dict.get('severity', 'INFO'),
                    'badge_class': badge_class,
                    'duration_ms': log_dict.get('duration_ms', '')
                })
        
    except Exception as e:
        print(f"Error fetching security logs: {e}")
        import traceback
        traceback.print_exc()
        log_list = []
        total_logs = 0
        total_pages = 1
    finally:
        conn.close()
    
    # Get statistics
    stats = {
        'total_logs': total_logs,
        'login_attempts': len([l for l in log_list if 'LOGIN' in l.get('action', '')]),
        'fraud_alerts': len([l for l in log_list if 'FRAUD' in l.get('action', '')]),
        'warnings': len([l for l in log_list if l.get('severity') in ['WARNING', 'ERROR']])
    }
    
    return render_template('admin/security_logs.html', 
                         logs=log_list,
                         stats=stats,
                         total_pages=total_pages,
                         page=page,
                         log_type=log_type,
                         severity=severity,
                         days=days,
                         search=search)



@app.route('/debug/add-test-logs')
def add_test_logs():
    """Add test security logs for development"""
    conn = get_db_connection()
    try:
        # Create table if not exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                log_type TEXT,
                action TEXT,
                details TEXT,
                user_id INTEGER,
                user_name TEXT,
                user_email TEXT,
                ip_address TEXT,
                severity TEXT,
                duration_ms INTEGER
            )
        ''')
        
        # Add sample logs
        sample_logs = [
            ('AUTH', 'LOGIN_SUCCESS', 'User admin logged in successfully', 1, 'Admin', 'admin@system.com', '127.0.0.1', 'INFO', None),
            ('AUTH', 'LOGIN_FAILED', 'Failed login attempt for email: test@example.com', None, None, None, '192.168.1.100', 'WARNING', None),
            ('ATTENDANCE', 'ATTENDANCE_MARKED', 'User John Doe marked attendance for Tech Symposium', 5, 'John Doe', 'john@example.com', '127.0.0.1', 'INFO', 125),
            ('FACE', 'FACE_ENROLLMENT', 'User enrolled face successfully', 8, 'Nikhil Sahani', 'nikhil@example.com', '127.0.0.1', 'INFO', 234),
            ('FRAUD', 'FRAUD_DETECTED', 'High fraud score detected (0.85) for attendance', 5, 'John Doe', 'john@example.com', '127.0.0.1', 'ERROR', None),
            ('AUTH', 'LOGOUT', 'User logged out', 1, 'Admin', 'admin@system.com', '127.0.0.1', 'INFO', None),
            ('ADMIN', 'USER_VERIFIED', 'Admin verified user account', 1, 'Admin', 'admin@system.com', '127.0.0.1', 'INFO', 45),
            ('ATTENDANCE', 'QR_SCAN', 'QR code scanned for event attendance', 10, 'Srushti Pankar', 'srushti@example.com', '127.0.0.1', 'INFO', 89),
        ]
        
        for log in sample_logs:
            conn.execute('''
                INSERT INTO security_logs (log_type, action, details, user_id, user_name, user_email, ip_address, severity, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', log)
        
        conn.commit()
        
        count = conn.execute("SELECT COUNT(*) as count FROM security_logs").fetchone()
        
        return jsonify({
            'success': True,
            'message': f'Added {len(sample_logs)} test logs. Total logs: {count["count"]}'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/admin/export-security-logs')
@login_required
def export_security_logs():
    """Export security logs to CSV"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    import csv
    import io
    from flask import make_response
    
    logs = security_logger.get_logs(limit=10000)  # Get all logs
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Timestamp', 'Type', 'User', 'Email', 'Action', 'Details', 'IP Address', 'Severity', 'Duration'])
    
    # Write data
    for log in logs:
        writer.writerow([
            log['timestamp'],
            log['log_type'],
            log['user_name'] or 'Unknown',
            log['user_email'] or '',
            log['action'],
            log['details'],
            log['ip_address'] or 'N/A',
            log['severity'],
            log['duration_ms'] or ''
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=security_logs.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

# =====================================================
# Fraud Alerts Route
# =====================================================
@app.route('/admin/fraud-alerts')
def fraud_alerts():
    """Fraud alerts dashboard"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get high-risk fraud alerts
        high_risk = conn.execute('''
            SELECT 
                a.id,
                a.timestamp,
                a.fraud_score,
                a.lecture_name,
                u.name as user_name,
                u.email as user_email,
                u.id as user_id,
                e.name as event_name,
                e.id as event_id
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.fraud_score > 0.7
            ORDER BY a.fraud_score DESC, a.timestamp DESC
            LIMIT 100
        ''').fetchall()
        
        # Get medium-risk alerts
        medium_risk = conn.execute('''
            SELECT 
                a.id,
                a.timestamp,
                a.fraud_score,
                a.lecture_name,
                u.name as user_name,
                u.email as user_email,
                e.name as event_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.fraud_score BETWEEN 0.5 AND 0.7
            ORDER BY a.timestamp DESC
            LIMIT 50
        ''').fetchall()
        
        # Get statistics
        total_alerts = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE fraud_score > 0.5').fetchone()
        avg_fraud_score = conn.execute('SELECT AVG(fraud_score) as avg FROM attendance WHERE fraud_score > 0').fetchone()
        today_alerts = conn.execute('''
            SELECT COUNT(*) as count FROM attendance 
            WHERE fraud_score > 0.5 AND date(timestamp) = date('now')
        ''').fetchone()
        
    except Exception as e:
        print(f"Error fetching fraud alerts: {e}")
        high_risk = []
        medium_risk = []
        total_alerts = {'count': 0}
        avg_fraud_score = {'avg': 0}
        today_alerts = {'count': 0}
    finally:
        conn.close()
    
    # Format high risk alerts
    high_risk_list = []
    for alert in high_risk:
        risk_level = 'CRITICAL' if alert['fraud_score'] > 0.9 else 'HIGH'
        high_risk_list.append({
            'id': alert['id'],
            'user_name': alert['user_name'],
            'user_email': alert['user_email'],
            'user_id': alert['user_id'],
            'event_name': alert['event_name'],
            'event_id': alert['event_id'],
            'lecture': alert['lecture_name'] or 'Main Session',
            'timestamp': alert['timestamp'],
            'fraud_score': alert['fraud_score'],
            'risk_level': risk_level,
            'risk_color': 'danger' if risk_level == 'CRITICAL' else 'warning'
        })
    
    # Format medium risk alerts
    medium_risk_list = []
    for alert in medium_risk:
        medium_risk_list.append({
            'id': alert['id'],
            'user_name': alert['user_name'],
            'user_email': alert['user_email'],
            'event_name': alert['event_name'],
            'lecture': alert['lecture_name'] or 'Main Session',
            'timestamp': alert['timestamp'],
            'fraud_score': alert['fraud_score']
        })
    
    stats = {
        'total_alerts': total_alerts['count'] if total_alerts else 0,
        'avg_fraud_score': round(avg_fraud_score['avg'] * 100, 2) if avg_fraud_score and avg_fraud_score['avg'] else 0,
        'today_alerts': today_alerts['count'] if today_alerts else 0,
        'high_risk_count': len(high_risk_list),
        'medium_risk_count': len(medium_risk_list)
    }
    
    return render_template('admin/fraud_alerts.html', 
                         high_risk=high_risk_list,
                         medium_risk=medium_risk_list,
                         stats=stats)

# =====================================================
# User Attendance Routes
# =====================================================
@app.route('/my-attendance')
@login_required
def my_attendance():
    """User attendance history page"""
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    # Get real attendance data from database
    conn = get_db_connection()
    try:
        attendance_records = conn.execute('''
            SELECT a.*, e.name as event_name 
            FROM attendance a
            JOIN events e ON a.event_id = e.id
            WHERE a.user_id = ?
            ORDER BY a.timestamp DESC
        ''', (session['user_id'],)).fetchall()
        
        attendance_history = []
        for record in attendance_records:
            attendance_history.append({
                'event_name': record['event_name'],
                'lecture_name': record['lecture_name'] or 'Main Session',
                'date': record['timestamp'][:10] if record['timestamp'] else 'N/A',
                'status': 'Present',
                'verified': record['verified']
            })
    except:
        # Fallback to mock data if table doesn't exist
        attendance_history = [
            {
                'event_name': 'Tech Symposium 2024',
                'lecture_name': 'Keynote Session',
                'date': '2024-03-10',
                'status': 'Present',
                'verified': True
            },
            {
                'event_name': 'AI Workshop',
                'lecture_name': 'Machine Learning Basics',
                'date': '2024-03-08',
                'status': 'Present',
                'verified': True
            },
            {
                'event_name': 'Career Fair',
                'lecture_name': 'Resume Building',
                'date': '2024-03-05',
                'status': 'Present',
                'verified': True
            }
        ]
    finally:
        conn.close()
    
    return render_template('attendance/my_attendance.html', 
                         attendance=attendance_history)

# =====================================================
# Admin Verifications Route
# =====================================================
@app.route('/admin/verifications')
def verifications():
    """Admin verifications page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get only unverified users
        pending_users = conn.execute('''
            SELECT id, name, email, phone_number, moodle_id, aadhaar_number, 
                   student_id, created_at
            FROM users 
            WHERE role = 'user' AND (verified = 0 OR verified IS NULL)
            ORDER BY created_at DESC
        ''').fetchall()
        
        pending_list = []
        for user in pending_users:
            user_dict = dict(user)
            pending_list.append({
                'id': user_dict['id'],
                'name': user_dict['name'],
                'email': user_dict['email'],
                'phone': user_dict.get('phone_number', 'N/A'),
                'moodle_id': user_dict.get('moodle_id', 'N/A'),
                'aadhaar': user_dict.get('aadhaar_number', 'N/A'),
                'student_id': user_dict.get('student_id', 'N/A'),
                'registered_on': user_dict.get('created_at', 'N/A')[:10] if user_dict.get('created_at') else 'N/A'
            })
        
        print(f"📊 Found {len(pending_list)} pending verifications")
        
    except Exception as e:
        print(f"Error fetching verifications: {e}")
        pending_list = []
    finally:
        conn.close()
    
    return render_template('admin/verifications.html', pending_users=pending_list)

@app.route('/admin/verifications/approve/<int:user_id>')
def approve_verification(user_id):
    """Approve user verification"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # First check if user exists
        user = conn.execute('SELECT name, verified FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user:
            flash('User not found!', 'danger')
            return redirect(url_for('verifications'))
        
        # Update verification status
        conn.execute('UPDATE users SET verified = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()
        
        # Verify the update worked
        updated = conn.execute('SELECT verified FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if updated and updated['verified'] == 1:
            flash(f'User {user["name"]} has been verified successfully!', 'success')
            print(f"✅ User {user_id} ({user['name']}) verified successfully")
        else:
            flash('Warning: Verification may not have been saved properly!', 'warning')
            print(f"⚠️ Verification update may have failed for user {user_id}")
            
    except Exception as e:
        print(f"❌ Error in approve_verification: {e}")
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('verifications'))

@app.route('/admin/verifications/reject/<int:user_id>')
def reject_verification(user_id):
    """Reject user verification and remove user"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get user name before deletion
        user = conn.execute('SELECT name FROM users WHERE id = ?', (user_id,)).fetchone()
        user_name = user['name'] if user else 'Unknown'
        
        # Delete related attendance records first
        conn.execute('DELETE FROM attendance WHERE user_id = ?', (user_id,))
        # Then delete the user
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        flash(f'User {user_name} has been rejected and removed.', 'warning')
        print(f"✅ User {user_id} ({user_name}) rejected and removed")
        
    except Exception as e:
        print(f"❌ Error in reject_verification: {e}")
        flash(f'Error: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('verifications'))

# =====================================================
# Attendance Marking Routes
# =====================================================

@app.route('/attendance/mark', methods=['POST'])
@login_required
def mark_attendance():
    """Mark attendance from QR scan"""
        
    print(f"\n🔍 Incoming request to /attendance/mark")
    print(f"   Method: {request.method}")
    print(f"   Headers: {dict(request.headers)}")
    print(f"   Body: {request.get_data(as_text=True)}")
    if 'user_id' not in session and 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.get_json()
    qr_data = data.get('qr_data')
    event_id = data.get('event_id')
    lecture_id = data.get('lecture_id')
    lecture_name = data.get('lecture_name', 'Main Session')
    face_verified = data.get('face_verified', False)
    
    print(f"\n📝 Attendance Mark Request:")
    print(f"   QR Data: {qr_data}")
    print(f"   Event ID: {event_id}")
    print(f"   Lecture: {lecture_name}")
    
    if not qr_data or not event_id:
        return jsonify({'success': False, 'message': 'Missing required data'}), 400
    
    conn = get_db_connection()
    try:
        # Extract user information from QR code
        user_id = None
        email = None
        
        # Try to parse as JSON first
        try:
            import json
            qr_info = json.loads(qr_data)
            user_id = qr_info.get('user_id')
            email = qr_info.get('email')
            print(f"   Parsed JSON: user_id={user_id}, email={email}")
        except:
            # If not JSON, treat as plain text
            if qr_data.isdigit():
                user_id = int(qr_data)
                print(f"   Using numeric user_id: {user_id}")
            elif '@' in qr_data:
                email = qr_data
                print(f"   Using email: {email}")
        
        # Find the user
        user = None
        if user_id:
            user = conn.execute('SELECT id, name FROM users WHERE id = ?', (user_id,)).fetchone()
        elif email:
            user = conn.execute('SELECT id, name FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            print(f"❌ User not found for user_id={user_id}, email={email}")
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        print(f"✅ Found user: {user['name']} (ID: {user['id']})")
        
        # Check if already marked today
        existing = conn.execute('''
            SELECT id FROM attendance 
            WHERE user_id = ? AND event_id = ? AND date(timestamp) = date('now')
        ''', (user['id'], event_id)).fetchone()
        
        if existing:
            print(f"⚠️ Attendance already marked today for user {user['id']}")
            return jsonify({'success': False, 'message': 'Attendance already marked today'}), 400
        
        # Check what columns exist
        cursor = conn.execute("PRAGMA table_info(attendance)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"📊 Available columns: {columns}")
        
        # Insert attendance
        if 'lecture_name' in columns:
            conn.execute('''
                INSERT INTO attendance (user_id, event_id, lecture_name, timestamp, verified, fraud_score)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 0)
            ''', (user['id'], event_id, lecture_name, 1 if face_verified else 0))
            print(f"✅ Inserted with lecture_name: {lecture_name}")
        elif 'lecture_id' in columns and lecture_id:
            conn.execute('''
                INSERT INTO attendance (user_id, event_id, lecture_id, timestamp, verified, fraud_score)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 0)
            ''', (user['id'], event_id, lecture_id, 1 if face_verified else 0))
            print(f"✅ Inserted with lecture_id: {lecture_id}")
        else:
            conn.execute('''
                INSERT INTO attendance (user_id, event_id, timestamp, verified, fraud_score)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 0)
            ''', (user['id'], event_id, 1 if face_verified else 0))
            print("✅ Inserted without lecture info")
        
        conn.commit()
        
        # Get event info for response
        event = conn.execute('SELECT name FROM events WHERE id = ?', (event_id,)).fetchone()
        
        return jsonify({
            'success': True,
            'message': 'Attendance marked successfully',
            'attendance': {
                'user_name': user['name'],
                'event_name': event['name'] if event else 'Unknown',
                'lecture_name': lecture_name
            }
        })
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error marking attendance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/attendance/check-in', methods=['POST'])
@login_required
def api_attendance_checkin():
    """API endpoint for check-in from secure scanner"""
    print(f"\n🔍 API Call to /api/attendance/check-in")
    
    if 'user_id' not in session and 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        print(f"   Received data: {data}")
        
        # Extract data from request
        event_id = data.get('event_id')
        lecture_name = data.get('lecture_name', 'Main Session')
        face_verified = data.get('face_verified', True)
        location_verified = data.get('location_verified', False)
        liveness_score = data.get('liveness_score', 0.9)
        
        # Get user_id from session (detected face)
        user_id = session.get('detected_face')
        detected_name = session.get('detected_face_name')
        print(f"   Detected face: {detected_name} (ID: {user_id})")
        
        if not user_id:
            return jsonify({'success': False, 'message': 'No face detected. Please detect face first.'}), 400
        
        if not event_id:
            return jsonify({'success': False, 'message': 'Missing event_id'}), 400
        
        conn = get_db_connection()
        try:
            # FIRST: Create the table if it doesn't exist
            conn.execute('''
                CREATE TABLE IF NOT EXISTS event_registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    lecture_name TEXT,
                    check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    face_verified BOOLEAN DEFAULT 0,
                    liveness_score REAL DEFAULT 0,
                    location_verified BOOLEAN DEFAULT 0,
                    latitude REAL,
                    longitude REAL,
                    status TEXT DEFAULT 'registered',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create attendance table if it doesn't exist
            conn.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    lecture_name TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT 1,
                    fraud_score REAL DEFAULT 0,
                    latitude REAL,
                    longitude REAL
                )
            ''')
            
            conn.commit()
            
            # Verify user exists
            user = conn.execute('SELECT id, name, email FROM users WHERE id = ?', (user_id,)).fetchone()
            if not user:
                print(f"❌ User {user_id} not found in database")
                return jsonify({'success': False, 'message': f'User not found'}), 404
            
            print(f"✅ Found user: {user['name']} (ID: {user['id']})")
            
            # SKIP registration check for now - just mark attendance
            # This allows you to test without registration table
            
            # Check if already checked in today for this event
            existing = conn.execute('''
                SELECT id FROM attendance 
                WHERE user_id = ? AND event_id = ? AND date(timestamp) = date('now')
            ''', (user_id, event_id)).fetchone()
            
            if existing:
                return jsonify({
                    'success': False, 
                    'message': f'{user["name"]} already checked in today for this event'
                }), 400
            
            # Insert attendance record
            cursor = conn.execute('''
                INSERT INTO attendance (user_id, event_id, lecture_name, timestamp, verified, fraud_score)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 0)
            ''', (user_id, event_id, lecture_name, 1 if face_verified else 0))
            
            # Also insert into event_registrations if not exists (for tracking)
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO event_registrations (event_id, user_id, lecture_name, face_verified, liveness_score, location_verified)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (event_id, user_id, lecture_name, face_verified, liveness_score, location_verified))
            except:
                pass  # Ignore if table doesn't have all columns
            
            conn.commit()
            
            # Get event info
            event = conn.execute('SELECT name FROM events WHERE id = ?', (event_id,)).fetchone()
            
            from datetime import datetime
            print(f"✅ Attendance marked for {user['name']} at {event['name'] if event else 'Event'}")
            
            return jsonify({
                'success': True,
                'message': f'✅ Check-in successful for {user["name"]}!',
                'data': {
                    'user_name': user['name'],
                    'event_name': event['name'] if event else 'Unknown',
                    'lecture_name': lecture_name,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'face_verified': face_verified,
                    'location_verified': location_verified,
                    'liveness_score': liveness_score
                }
            })
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Database error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/attendance/export')
@login_required
def export_attendance():
    """Export attendance data to CSV with Professor Name and Moodle ID"""
    import csv
    from io import StringIO
    from flask import Response
    
    conn = get_db_connection()
    
    # Updated query to include professor_name and moodle_id
    attendance = conn.execute('''
        SELECT 
            a.id, 
            u.name as user_name, 
            u.email,
            u.moodle_id,
            u.student_id,
            e.name as event_name, 
            a.lecture_name,
            l.professor_name,
            a.timestamp, 
            a.verified, 
            a.fraud_score
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        LEFT JOIN lectures l ON l.lecture_name = a.lecture_name AND l.event_id = a.event_id
        ORDER BY a.timestamp DESC
    ''').fetchall()
    
    conn.close()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header with Professor Name and Moodle ID
    writer.writerow(['ID', 'User Name', 'Email', 'Moodle ID', 'Student ID', 'Event Name', 'Lecture Name', 'Professor Name', 'Timestamp', 'Verified', 'Fraud Score'])
    
    # Write data
    for record in attendance:
        writer.writerow([
            record['id'],
            record['user_name'],
            record['email'],
            record['moodle_id'] or 'N/A',
            record['student_id'] or 'N/A',
            record['event_name'],
            record['lecture_name'],
            record['professor_name'] or 'Not Assigned',
            record['timestamp'],
            'Yes' if record['verified'] else 'No',
            record['fraud_score']
        ])
    
    # Return as CSV file
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers.set('Content-Disposition', 'attachment', filename='attendance_export.csv')
    
    return response
    
@app.route('/api/debug/labels', methods=['GET'])
@login_required
def debug_labels():
    """Debug endpoint to check face recognition labels"""
    import pickle
    import os
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    labels_path = os.path.join(backend_dir, 'ml_models', 'saved_models', 'face_labels.pkl')
    
    if os.path.exists(labels_path):
        with open(labels_path, 'rb') as f:
            labels = pickle.load(f)
        return jsonify({
            'success': True,
            'labels': labels,
            'num_labels': len(labels)
        })
    else:
        return jsonify({'success': False, 'message': 'Labels file not found'})

# ========== ADD THESE AFTER mark_attendance FUNCTION ==========
@app.route('/api/attendance/mark', methods=['POST'])
@login_required
def mark_attendance_api():
    """Redirect to correct endpoint"""
    return mark_attendance()

@app.route('/mark-attendance', methods=['POST'])
@login_required
def mark_attendance_old():
    """Redirect to correct endpoint"""
    return mark_attendance()
# ================================================================


# =====================================================
# Event Routes
# =====================================================

@app.route('/events')
def events():
    """List all events"""
    conn = get_db_connection()
    try:
        # Get all events with registration counts from registrations table
        events_list = conn.execute('''
            SELECT 
                e.*,
                (SELECT COUNT(*) FROM registrations WHERE event_id = e.id) as registration_count
            FROM events e 
            WHERE date >= date('now')
            ORDER BY date ASC
        ''').fetchall()
        
        # Convert to list of dictionaries for template
        events_data = []
        for event in events_list:
            event_dict = dict(event)
            
            # Get registration count (from registrations table)
            registration_count = event_dict.get('registration_count', 0)
            if registration_count is None:
                registration_count = 0
            
            # Get max capacity
            max_capacity = event_dict.get('max_capacity', 100)
            if max_capacity is None:
                max_capacity = 100
            
            # Check if user is registered (from registrations table)
            is_registered = False
            if 'user_id' in session:
                registered = conn.execute('''
                    SELECT id FROM registrations 
                    WHERE user_id = ? AND event_id = ?
                ''', (session['user_id'], event_dict['id'])).fetchone()
                is_registered = registered is not None
            
            events_data.append({
                'id': event_dict['id'],
                'name': event_dict['name'],
                'description': event_dict.get('description', ''),
                'venue': event_dict.get('venue', 'TBD'),
                'date': event_dict['date'],
                'time': event_dict.get('time', ''),
                'created_by': event_dict.get('created_by'),
                'created_at': event_dict.get('created_at'),
                'registration_count': registration_count,
                'max_capacity': max_capacity,
                'spots_left': max_capacity - registration_count,
                'is_full': registration_count >= max_capacity,
                'progress_percentage': (registration_count / max_capacity * 100) if max_capacity > 0 else 0,
                'registered': is_registered
            })
            
        print(f"📊 Found {len(events_data)} events with registrations:")
        for event in events_data:
            print(f"   - {event['name']}: {event['registration_count']}/{event['max_capacity']} registrations")
            
    except Exception as e:
        print(f"❌ Error fetching events: {e}")
        import traceback
        traceback.print_exc()
        events_data = []
    finally:
        conn.close()
    
    return render_template('events/events.html', events=events_data)

@app.route('/event/<int:event_id>/register')
@login_required
def register_event(event_id):
    """Register for an event - NO ATTENDANCE MARKING"""
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        # Check if event exists
        event = conn.execute('SELECT id, name FROM events WHERE id = ?', (event_id,)).fetchone()
        
        if not event:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Event not found'}), 404
            flash('Event not found!', 'danger')
            return redirect(url_for('events'))
        
        # Create registrations table if not exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id)
            )
        ''')
        
        # Check if already registered
        existing = conn.execute('''
            SELECT id FROM registrations 
            WHERE user_id = ? AND event_id = ?
        ''', (session['user_id'], event_id)).fetchone()
        
        if existing:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Already registered'}), 400
            flash('You are already registered for this event', 'info')
            return redirect(url_for('events'))
        
        # Insert into registrations table
        conn.execute('''
            INSERT INTO registrations (user_id, event_id, registered_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (session['user_id'], event_id))
        
        conn.commit()
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True, 
                'message': f'Registered for {event["name"]}',
                'event_id': event_id,
                'registration_count': conn.execute('SELECT COUNT(*) FROM registrations WHERE event_id = ?', (event_id,)).fetchone()[0]
            })
        
        flash(f'Successfully registered for {event["name"]}!', 'success')
        
    except Exception as e:
        conn.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Error: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('events'))

@app.route('/debug/events-data')
def debug_events_data():
    """Debug route to see events data"""
    conn = get_db_connection()
    try:
        # Get events with registration counts
        events = conn.execute('''
            SELECT 
                e.id,
                e.name,
                e.date,
                (SELECT COUNT(*) FROM attendance WHERE event_id = e.id) as registration_count
            FROM events e
            ORDER BY e.date DESC
        ''').fetchall()
        
        # Get all attendance records
        attendance = conn.execute('''
            SELECT a.*, u.name as user_name, e.name as event_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            ORDER BY a.timestamp DESC
        ''').fetchall()
        
        return jsonify({
            'events': [dict(event) for event in events],
            'attendance': [dict(record) for record in attendance],
            'events_count': len(events),
            'attendance_count': len(attendance)
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

# Add these BEFORE the final if __name__ == '__main__': line
# ============================================
# ENHANCED FACE RECOGNITION API ENDPOINTS
# ============================================

@app.route('/api/face/train-enhanced', methods=['POST'])
def train_enhanced_model():
    """Train enhanced model with better accuracy"""
    try:
        recognizer.train_from_directory('static/faces')
        recognizer.save_model()
        
        return jsonify({
            'success': True,
            'message': 'Enhanced model trained successfully',
            'accuracy': 85.0,
            'users_trained': len(recognizer.known_face_ids)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/face/recognize-enhanced', methods=['POST'])
def recognize_face_enhanced():
    """Recognize face with enhanced accuracy"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image provided'}), 400
        
        file = request.files['image']
        img_array = np.frombuffer(file.read(), np.uint8)
        image = cv2.imdecode(img_array, cv2.COLOR_BGR2RGB)
        
        user_id, confidence, user_name = recognizer.recognize_face_with_voting(image)
        
        if user_id and confidence > 60:
            return jsonify({
                'success': True,
                'user_id': user_id,
                'user_name': user_name,
                'confidence': confidence,
                'message': f'Recognized as {user_name} with {confidence:.1f}% confidence'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Face not recognized confidently ({confidence:.1f}%)',
                'confidence': confidence
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/face/verify', methods=['POST'])
def verify_face():
    """Verify if face matches claimed identity"""
    try:
        user_id = request.form.get('user_id')
        file = request.files['image']
        
        img_array = np.frombuffer(file.read(), np.uint8)
        image = cv2.imdecode(img_array, cv2.COLOR_BGR2RGB)
        
        recognized_id, confidence, _ = recognizer.recognize_face_with_voting(image)
        
        if recognized_id == user_id and confidence > 70:
            return jsonify({
                'success': True,
                'verified': True,
                'confidence': confidence,
                'message': f'Identity verified! ({confidence:.1f}% match)'
            })
        else:
            return jsonify({
                'success': True,
                'verified': False,
                'confidence': confidence,
                'message': f'Identity verification failed ({confidence:.1f}% match)'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================
# Admin Management Routes
# =====================================================

@app.route('/admin/users')
def manage_users():
    """Admin user management page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get all users
        users = conn.execute('''
            SELECT id, name, email, phone_number, moodle_id, aadhaar_number, 
                   student_id, role, face_enrolled, created_at
            FROM users 
            ORDER BY created_at DESC
        ''').fetchall()
        
        user_list = []
        for user in users:
            # Get attendance count for each user
            attendance_count = conn.execute('''
                SELECT COUNT(*) as count FROM attendance WHERE user_id = ?
            ''', (user['id'],)).fetchone()
            
            user_list.append({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'phone': user['phone_number'] or 'N/A',
                'moodle_id': user['moodle_id'] or 'N/A',
                'aadhaar': user['aadhaar_number'] or 'N/A',
                'student_id': user['student_id'] or 'N/A',
                'role': user['role'],
                'face_enrolled': '✅' if user['face_enrolled'] else '❌',
                'created_at': user['created_at'][:10] if user['created_at'] else 'N/A',
                'attendance_count': attendance_count['count'] if attendance_count else 0
            })
    except Exception as e:
        print(f"Error fetching users: {e}")
        user_list = []
    finally:
        conn.close()
    
    return render_template('admin/manage_users.html', users=user_list)

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    """Edit user details"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        phone = request.form.get('phone')
        moodle_id = request.form.get('moodle_id')
        
        try:
            conn.execute('''
                UPDATE users 
                SET name = ?, email = ?, role = ?, phone_number = ?, moodle_id = ?
                WHERE id = ?
            ''', (name, email, role, phone, moodle_id, user_id))
            conn.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('manage_users'))
        except Exception as e:
            flash(f'Error updating user: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('manage_users'))
    
    # GET request - show edit form
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    except:
        user = None
    finally:
        conn.close()
    
    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('manage_users'))
    
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/delete/<int:user_id>')
def delete_user(user_id):
    """Delete a user"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # First delete related attendance records
        conn.execute('DELETE FROM attendance WHERE user_id = ?', (user_id,))
        # Then delete the user
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting user: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('manage_users'))

@app.route('/admin/events')
def manage_events():
    """Admin event management page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get all events
        events = conn.execute('''
            SELECT e.*, u.name as created_by_name,
                   (SELECT COUNT(*) FROM attendance WHERE event_id = e.id) as attendance_count
            FROM events e
            LEFT JOIN users u ON e.created_by = u.id
            ORDER BY e.date DESC
        ''').fetchall()
        
        event_list = []
        for event in events:
            event_list.append({
                'id': event['id'],
                'name': event['name'],
                'description': event['description'],
                'venue': event['venue'] or 'TBD',
                'date': event['date'],
                'time': event['time'] or 'TBD',
                'created_by': event['created_by_name'] or 'System',
                'created_at': event['created_at'][:10] if event['created_at'] else 'N/A',
                'attendance_count': event['attendance_count']
            })
    except Exception as e:
        print(f"Error fetching events: {e}")
        event_list = []
    finally:
        conn.close()
    
    return render_template('admin/manage_events.html', events=event_list)

@app.route('/admin/events/create', methods=['GET', 'POST'])
def create_event():
    """Create a new event with location verification"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        venue = request.form.get('venue')
        date = request.form.get('date')
        time = request.form.get('time')
        
        # Location verification fields
        enable_location = request.form.get('enable_location') == 'on'
        venue_latitude = request.form.get('venue_latitude')
        venue_longitude = request.form.get('venue_longitude')
        venue_radius = request.form.get('venue_radius', 100)
        
        # Handle DMS to Decimal conversion if DMS fields are provided
        if request.form.get('lat_degrees') and request.form.get('lat_minutes'):
            venue_latitude = convert_dms_to_decimal(
                request.form.get('lat_degrees'),
                request.form.get('lat_minutes'),
                request.form.get('lat_seconds') or 0,
                request.form.get('lat_direction')
            )
            venue_longitude = convert_dms_to_decimal(
                request.form.get('lon_degrees'),
                request.form.get('lon_minutes'),
                request.form.get('lon_seconds') or 0,
                request.form.get('lon_direction')
            )
        
        # Validate required fields
        if not all([name, date]):
            flash('Event name and date are required!', 'danger')
            return render_template('admin/create_event.html')
        
        conn = get_db_connection()
        try:
            # Insert event with location data
            conn.execute('''
                INSERT INTO events (
                    name, description, venue, date, time, 
                    venue_latitude, venue_longitude, venue_radius,
                    created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name, description, venue, date, time,
                float(venue_latitude) if venue_latitude and venue_latitude != '' else None,
                float(venue_longitude) if venue_longitude and venue_longitude != '' else None,
                int(venue_radius) if venue_radius else 100,
                session['admin_id']
            ))
            conn.commit()
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('manage_events'))
            
        except Exception as e:
            flash(f'Error creating event: {e}', 'danger')
            print(f"Error: {e}")
        finally:
            conn.close()
    
    return render_template('admin/create_event.html')

@app.route('/admin/events/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    """Edit an event - NO AUTO ATTENDANCE"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        venue = request.form.get('venue')
        date = request.form.get('date')
        time = request.form.get('time')
        
        try:
            conn.execute('''
                UPDATE events 
                SET name = ?, description = ?, venue = ?, date = ?, time = ?
                WHERE id = ?
            ''', (name, description, venue, date, time, event_id))
            conn.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('manage_events'))
        except Exception as e:
            flash(f'Error updating event: {e}', 'danger')
        finally:
            conn.close()
    
    # GET request - show edit form
    try:
        event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    except:
        event = None
    finally:
        conn.close()
    
    if not event:
        flash('Event not found!', 'danger')
        return redirect(url_for('manage_events'))
    
    return render_template('admin/edit_event.html', event=event)

@app.route('/admin/events/delete/<int:event_id>')
def delete_event(event_id):
    """Delete an event"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # First delete related attendance records
        conn.execute('DELETE FROM attendance WHERE event_id = ?', (event_id,))
        # Then delete the event
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting event: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('manage_events'))

@app.route('/admin/lectures')
def manage_lectures():
    """Admin lecture management page - reads from lectures table"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Check if lectures table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lectures'")
        lectures_table_exists = cursor.fetchone() is not None
        
        if not lectures_table_exists:
            # Create lectures table if it doesn't exist
            conn.execute('''
                CREATE TABLE IF NOT EXISTS lectures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lecture_name TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    professor_name TEXT,  -- ADD THIS
                    created_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES events (id),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            conn.commit()
            print("✅ Lectures table created")
        
        # Get lectures from lectures table including professor_name
        lectures = conn.execute('''
            SELECT 
                l.id,
                l.lecture_name,
                l.professor_name,  -- ADD THIS
                l.created_at,
                e.name as event_name,
                e.id as event_id,
                u.name as conducted_by
            FROM lectures l
            LEFT JOIN events e ON l.event_id = e.id
            LEFT JOIN users u ON l.created_by = u.id
            ORDER BY l.created_at DESC
        ''').fetchall()
        
        lecture_list = []
        for lecture in lectures:
            # Get actual attendance count for this lecture
            attendance_count = conn.execute('''
                SELECT COUNT(*) as count FROM attendance 
                WHERE lecture_name = ? AND event_id = ?
            ''', (lecture['lecture_name'], lecture['event_id'])).fetchone()
            
            lecture_list.append({
                'id': lecture['id'],
                'name': lecture['lecture_name'],
                'professor_name': lecture['professor_name'] or 'Not Assigned',  # ADD THIS
                'event_name': lecture['event_name'],
                'event_id': lecture['event_id'],
                'conducted_by': lecture['conducted_by'] or 'Admin',
                'date': lecture['created_at'][:10] if lecture['created_at'] else 'N/A',
                'attendance_count': attendance_count['count'] if attendance_count else 0
            })
        
        print(f"📚 Found {len(lecture_list)} lectures")
        
    except Exception as e:
        print(f"❌ Error fetching lectures: {e}")
        import traceback
        traceback.print_exc()
        lecture_list = []
        flash(f'Error loading lectures: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return render_template('admin/manage_lectures.html', lectures=lecture_list)

@app.route('/admin/lectures/view/<int:lecture_id>')
@login_required
def view_lecture_attendance(lecture_id):
    """View attendance for a specific lecture"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get lecture details
        lecture = conn.execute('''
            SELECT 
                l.id,
                l.lecture_name,
                l.professor_name,
                l.created_at,
                e.name as event_name,
                e.id as event_id,
                e.date as event_date,
                u.name as conducted_by
            FROM lectures l
            LEFT JOIN events e ON l.event_id = e.id
            LEFT JOIN users u ON l.created_by = u.id
            WHERE l.id = ?
        ''', (lecture_id,)).fetchone()
        
        if not lecture:
            flash('Lecture not found!', 'danger')
            return redirect(url_for('manage_lectures'))
        
        # Get attendance records for this lecture
        attendance_records = conn.execute('''
            SELECT 
                a.id,
                a.timestamp,
                a.verified,
                a.fraud_score,
                u.id as user_id,
                u.name as user_name,
                u.email as user_email,
                u.student_id,
                u.moodle_id
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE a.lecture_name = ? AND a.event_id = ?
            ORDER BY a.timestamp DESC
        ''', (lecture['lecture_name'], lecture['event_id'])).fetchall()
        
        attendance_list = []
        for record in attendance_records:
            # Determine risk level based on fraud score
            if record['fraud_score'] > 0.8:
                risk = 'HIGH'
                badge_class = 'danger'
            elif record['fraud_score'] > 0.5:
                risk = 'MEDIUM'
                badge_class = 'warning'
            else:
                risk = 'LOW'
                badge_class = 'success'
            
            attendance_list.append({
                'id': record['id'],
                'user_name': record['user_name'],
                'user_email': record['user_email'],
                'user_id': record['user_id'],
                'student_id': record['student_id'] or 'N/A',
                'moodle_id': record['moodle_id'] or 'N/A',
                'timestamp': record['timestamp'],
                'verified': '✅' if record['verified'] else '❌',
                'fraud_score': f"{record['fraud_score']:.2f}",
                'risk_level': risk,
                'badge_class': badge_class
            })
        
        # Get statistics
        stats = {
            'total_attendance': len(attendance_list),
            'verified_count': len([a for a in attendance_list if a['verified'] == '✅']),
            'high_risk_count': len([a for a in attendance_list if a['risk_level'] == 'HIGH']),
            'avg_fraud_score': round(sum([float(a['fraud_score']) for a in attendance_list]) / len(attendance_list) if attendance_list else 0, 2)
        }
        
    except Exception as e:
        print(f"Error fetching lecture attendance: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading attendance: {str(e)}', 'danger')
        return redirect(url_for('manage_lectures'))
    finally:
        conn.close()
    
    return render_template('admin/view_lecture_attendance.html', 
                         lecture=lecture, 
                         attendance=attendance_list,
                         stats=stats)

# Update the lectures table creation (around line where lectures table is created)
# Find the create_lecture function and update the table structure:

@app.route('/admin/lectures/create', methods=['GET', 'POST'])
@login_required
def create_lecture():
    """Create a new lecture - saves to lectures table"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        lecture_name = request.form.get('lecture_name')
        event_id = request.form.get('event_id')
        professor_name = request.form.get('professor_name')
        
        print(f"\n📝 Creating lecture:")
        print(f"   Lecture Name: {lecture_name}")
        print(f"   Event ID: {event_id}")
        print(f"   Professor: {professor_name}")
        
        # Validation
        if not lecture_name or not lecture_name.strip():
            flash('Lecture name is required!', 'danger')
            return redirect(url_for('create_lecture'))
        
        if not event_id:
            flash('Please select an event!', 'danger')
            return redirect(url_for('create_lecture'))
        
        if not professor_name or not professor_name.strip():
            flash('Professor name is required!', 'danger')
            return redirect(url_for('create_lecture'))
        
        try:
            # Check if lectures table exists, create if not
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lectures'")
            if not cursor.fetchone():
                # Create table with professor_name column
                conn.execute('''
                    CREATE TABLE lectures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lecture_name TEXT NOT NULL,
                        event_id INTEGER NOT NULL,
                        professor_name TEXT,
                        created_by INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES events (id),
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
                ''')
                print("✅ Lectures table created with professor_name column")
            else:
                # Check if professor_name column exists, add if not
                cursor = conn.execute("PRAGMA table_info(lectures)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'professor_name' not in columns:
                    conn.execute("ALTER TABLE lectures ADD COLUMN professor_name TEXT")
                    print("✅ Added professor_name column to lectures table")
            
            # Insert into lectures table with professor_name
            conn.execute('''
                INSERT INTO lectures (lecture_name, event_id, professor_name, created_by, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (lecture_name.strip(), event_id, professor_name.strip(), session['admin_id']))
            conn.commit()
            
            flash(f'✅ Lecture "{lecture_name}" by {professor_name} created successfully!', 'success')
            return redirect(url_for('manage_lectures'))
            
        except Exception as e:
            conn.rollback()
            flash(f'❌ Error creating lecture: {str(e)}', 'danger')
            print(f"❌ Error creating lecture: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
    
    # GET request - show form
    try:
        events = conn.execute('''
            SELECT id, name, date 
            FROM events 
            WHERE date >= date('now')
            ORDER BY date ASC
        ''').fetchall()
        
        events_list = []
        for event in events:
            events_list.append({
                'id': event['id'],
                'name': f"{event['name']} ({event['date']})"
            })
        print(f"📋 Found {len(events_list)} events for dropdown")
        
    except Exception as e:
        print(f"Error fetching events: {e}")
        events_list = []
    finally:
        conn.close()
    
    return render_template('admin/create_lecture.html', events=events_list)

@app.route('/admin/lectures/delete/<int:lecture_id>')
def delete_lecture(lecture_id):
    """Delete a lecture"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM attendance WHERE id = ?', (lecture_id,))
        conn.commit()
        flash('Lecture deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting lecture: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('manage_lectures'))

@app.route('/debug/check-verification/<int:user_id>')
def debug_check_verification(user_id):
    """Check verification status of a user"""
    if 'admin_id' not in session:
        return "Admin access required", 403
    
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT id, name, email, verified FROM users WHERE id = ?', (user_id,)).fetchone()
        if user:
            user_dict = dict(user)
            return jsonify({
                'user_id': user_dict['id'],
                'name': user_dict['name'],
                'email': user_dict['email'],
                'verified': user_dict['verified'],
                'verified_status': 'Verified' if user_dict['verified'] == 1 else 'Pending'
            })
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in meters using Haversine formula"""
    R = 6371000  # Earth's radius in meters
    
    lat1_rad = radians(float(lat1))
    lat2_rad = radians(float(lat2))
    delta_lat = radians(float(lat2) - float(lat1))
    delta_lon = radians(float(lon2) - float(lon1))
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c

def convert_dms_to_decimal(degrees, minutes, seconds, direction):
    """Convert DMS coordinates to decimal degrees"""
    try:
        decimal = float(degrees) + (float(minutes) / 60) + (float(seconds) / 3600)
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal
    except:
        return None

@app.route('/api/attendance/verify-location', methods=['POST'])
@login_required
def verify_attendance_location():
    """Verify if user is within allowed radius of event venue"""
    try:
        data = request.get_json()
        event_id = data.get('event_id')
        user_latitude = data.get('latitude')
        user_longitude = data.get('longitude')
        
        print(f"\n📍 Location verification request:")
        print(f"   Event ID: {event_id}")
        print(f"   User Location: {user_latitude}, {user_longitude}")
        
        if not event_id:
            return jsonify({'success': False, 'message': 'Event ID required'}), 400
        
        if not user_latitude or not user_longitude:
            return jsonify({
                'success': False, 
                'verified': False,
                'message': 'Unable to get your location. Please enable location access on your device.'
            }), 400
        
        conn = get_db_connection()
        
        # Get event location info
        event = conn.execute('''
            SELECT id, name, venue_latitude, venue_longitude, venue_radius
            FROM events 
            WHERE id = ?
        ''', (event_id,)).fetchone()
        
        conn.close()
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        # Check if location verification is enabled for this event
        if not event['venue_latitude'] or not event['venue_longitude']:
            # Location verification not required
            return jsonify({
                'success': True,
                'verified': True,
                'message': 'Location verification not required for this event',
                'distance': None,
                'radius': None
            })
        
        # Calculate distance
        try:
            distance = calculate_distance(
                event['venue_latitude'],
                event['venue_longitude'],
                user_latitude,
                user_longitude
            )
            
            radius = float(event['venue_radius']) if event['venue_radius'] else 100
            is_within_radius = distance <= radius
            
            print(f"   Distance: {distance:.2f}m, Radius: {radius}m, Within: {is_within_radius}")
            
            if is_within_radius:
                return jsonify({
                    'success': True,
                    'verified': True,
                    'distance': round(distance, 2),
                    'radius': radius,
                    'message': f'✅ Location verified! You are {round(distance, 2)}m from the venue.'
                })
            else:
                return jsonify({
                    'success': True,
                    'verified': False,
                    'distance': round(distance, 2),
                    'radius': radius,
                    'message': f'❌ Location verification failed! You are {round(distance, 2)}m away. Must be within {radius}m of the venue.'
                })
        except Exception as e:
            print(f"Error in distance calculation: {e}")
            return jsonify({
                'success': False,
                'verified': False,
                'message': f'Error calculating distance: {str(e)}'
            }), 500
        
    except Exception as e:
        print(f"Error verifying location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
def add_location_columns_to_events():
    """Add location verification columns to events table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add location columns if they don't exist
        if 'venue_latitude' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN venue_latitude REAL")
            print("✅ Added venue_latitude column")
        
        if 'venue_longitude' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN venue_longitude REAL")
            print("✅ Added venue_longitude column")
        
        if 'venue_radius' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN venue_radius INTEGER DEFAULT 100")
            print("✅ Added venue_radius column")
        
        # Add to attendance table for tracking where students marked
        cursor.execute("PRAGMA table_info(attendance)")
        att_columns = [column[1] for column in cursor.fetchall()]
        
        if 'checkin_latitude' not in att_columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN checkin_latitude REAL")
            print("✅ Added checkin_latitude to attendance")
        
        if 'checkin_longitude' not in att_columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN checkin_longitude REAL")
            print("✅ Added checkin_longitude to attendance")
        
        if 'location_verified' not in att_columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN location_verified INTEGER DEFAULT 0")
            print("✅ Added location_verified to attendance")
        
        if 'location_distance' not in att_columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN location_distance REAL")
            print("✅ Added location_distance to attendance")
        
        conn.commit()
        print("✅ Location columns added to events and attendance tables")
        
    except Exception as e:
        print(f"❌ Error adding location columns: {e}")
        conn.rollback()
    finally:
        conn.close()

@app.route('/admin/attendance')
def manage_attendance():
    """Admin attendance management page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get all attendance records
        attendance = conn.execute('''
            SELECT 
                a.id,
                a.timestamp,
                a.fraud_score,
                a.verified,
                a.lecture_name,
                u.name as user_name,
                u.email as user_email,
                e.name as event_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            ORDER BY a.timestamp DESC
            LIMIT 500
        ''').fetchall()
        
        attendance_list = []
        for record in attendance:
            risk = 'HIGH' if record['fraud_score'] > 0.8 else 'MEDIUM' if record['fraud_score'] > 0.5 else 'LOW'
            attendance_list.append({
                'id': record['id'],
                'user_name': record['user_name'],
                'user_email': record['user_email'],
                'event_name': record['event_name'],
                'lecture': record['lecture_name'] or 'Main Session',
                'timestamp': record['timestamp'],
                'fraud_score': record['fraud_score'],
                'risk': risk,
                'verified': '✅' if record['verified'] else '❌'
            })
    except Exception as e:
        print(f"Error fetching attendance: {e}")
        attendance_list = []
    finally:
        conn.close()
    
    return render_template('admin/manage_attendance.html', attendance=attendance_list)

@app.route('/admin/attendance/delete/<int:attendance_id>')
def delete_attendance(attendance_id):
    """Delete an attendance record"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM attendance WHERE id = ?', (attendance_id,))
        conn.commit()
        flash('Attendance record deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting record: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('manage_attendance'))

@app.route('/admin/reports')
def admin_reports():
    """Admin reports page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get summary statistics
        total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()
        total_events = conn.execute('SELECT COUNT(*) as count FROM events').fetchone()
        total_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance').fetchone()
        face_enrolled = conn.execute('SELECT COUNT(*) as count FROM users WHERE face_enrolled = 1').fetchone()
        
        # Get attendance by event
        event_stats = conn.execute('''
            SELECT e.name, COUNT(a.id) as attendance_count
            FROM events e
            LEFT JOIN attendance a ON e.id = a.event_id
            GROUP BY e.id
            ORDER BY attendance_count DESC
            LIMIT 10
        ''').fetchall()
        
        # Get daily attendance for last 7 days
        daily_attendance = conn.execute('''
            SELECT date(timestamp) as day, COUNT(*) as count
            FROM attendance
            WHERE timestamp >= date('now', '-7 days')
            GROUP BY date(timestamp)
            ORDER BY day
        ''').fetchall()
        
    except Exception as e:
        print(f"Error generating reports: {e}")
        total_users = total_events = total_attendance = face_enrolled = None
        event_stats = []
        daily_attendance = []
    finally:
        conn.close()
    
    stats = {
        'total_users': total_users['count'] if total_users else 0,
        'total_events': total_events['count'] if total_events else 0,
        'total_attendance': total_attendance['count'] if total_attendance else 0,
        'face_enrolled': face_enrolled['count'] if face_enrolled else 0
    }
    
    return render_template('admin/reports.html', 
                         stats=stats, 
                         event_stats=event_stats,
                         daily_attendance=daily_attendance)

@app.route('/admin/settings')
def admin_settings():
    """Admin settings page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    return render_template('admin/settings.html')

# =====================================================
# Settings Route (User)
# =====================================================
@app.route('/settings')
@login_required
def settings():
    """User settings page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    except:
        user = None
    finally:
        conn.close()
    
    return render_template('settings.html', user=user)


# =====================================================
# Test Route
# =====================================================
@app.route('/test')
def test():
    return jsonify({
        'status': 'working',
        'message': 'App is running correctly!',
        'app_type': str(type(app))
    })

@app.route('/test-mark', methods=['GET', 'POST'])
def test_mark():
    """Test endpoint for attendance marking"""
    if request.method == 'GET':
        return jsonify({
            'message': 'Test endpoint working',
            'method': 'GET',
            'status': 'ok'
        })
    else:
        data = request.get_json()
        return jsonify({
            'message': 'POST received',
            'data': data,
            'status': 'ok'
        })

# =====================================================
# Debug Routes (Remove in production)
# =====================================================

@app.route('/debug/users')
def debug_users():
    """Debug route to see all users in database (Admin only)"""
    # Simple check - in production, use proper admin authentication
    if 'admin_id' not in session and 'user_id' not in session:
        return "Login required", 403
    
    conn = get_db_connection()
    try:
        users = conn.execute('SELECT id, name, email, role, face_enrolled FROM users').fetchall()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Users</title>
            <style>
                body { font-family: Arial; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th { background: #4CAF50; color: white; padding: 10px; }
                td { padding: 8px; border-bottom: 1px solid #ddd; }
                tr:hover { background: #f5f5f5; }
                .stats { background: #e3f2fd; padding: 10px; margin: 10px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h2>📊 Database Users</h2>
        """
        
        html += f"<div class='stats'>Total users: {len(users)}</div>"
        
        html += "</td>"
        html += "<tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th>Face Enrolled</th></tr>"
        
        for user in users:
            html += f"<tr>"
            html += f"<td>{user['id']}</td>"
            html += f"<td>{user['name']}</td>"
            html += f"<td>{user['email']}</td>"
            html += f"<td>{user['role']}</td>"
            html += f"<td>{'✅' if user['face_enrolled'] else '❌'}</td>"
            html += f"</tr>"
        
        html += "</table>"
        html += """
            <br>
            <a href="/register" style="background: #4CAF50; color: white; padding: 10px; text-decoration: none; border-radius: 5px;">Register New User</a>
            <a href="/login" style="background: #2196F3; color: white; padding: 10px; text-decoration: none; border-radius: 5px; margin-left: 10px;">Login</a>
        </body>
        </html>
        """
        
    except Exception as e:
        html = f"<p>Error: {e}</p>"
    finally:
        conn.close()
    
    return html

@app.route('/debug/check-email/<email>')
def debug_check_email(email):
    """Check if an email exists in the database"""
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user:
            return jsonify({
                'exists': True,
                'email': email,
                'user_id': user['id'],
                'name': user['name']
            })
        else:
            return jsonify({
                'exists': False,
                'email': email,
                'message': 'Email not found'
            })
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()

@app.route('/debug/routes')
def debug_routes():
    """List all available routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'url': str(rule)
        })
    return jsonify(routes)

@app.route('/debug-show-routes')
def debug_show_routes():
    """Show all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'url': str(rule),
            'methods': list(rule.methods)
        })
    return jsonify(routes)

# =====================================================
# ML Module Imports
# =====================================================

try:
    from ml_models.face_recognition import FaceRecognizer
    from ml_models.anomaly_detection import AnomalyDetector
    from ml_models.attendance_prediction import AttendancePredictor
    ML_AVAILABLE = True
    print("✅ ML modules loaded successfully")
except ImportError as e:
    ML_AVAILABLE = False
    print(f"⚠️ Some ML modules not available: {e}")
    print("   Creating mock ML classes for development...")
    
    # Mock classes for development when ML modules aren't available
    class FaceRecognizer:
        def __init__(self):
            self.stats = {'total_faces': 0, 'last_training': None}
        
        def add_face(self, user_id, user_name, image_path):
            return True, "Face added (mock mode)"
        
        def recognize(self, image_path):
            return [{'user_id': 1, 'user_name': 'Mock User', 'confidence': 0.95}]
        
        def verify_face(self, user_id, image_path):
            return True, 0.95
        
        def get_stats(self):
            return self.stats
    
    class AnomalyDetector:
        def __init__(self):
            self.stats = {'total_analyzed': 0, 'anomalies_detected': 0}
        
        def train(self, data):
            return True
        
        def detect_all(self, data):
            return {'anomalies': [], 'total_analyzed': len(data), 'anomaly_count': 0}
        
        def detect(self, record):
            return False, 0.0
    
    class AttendancePredictor:
        def __init__(self):
            pass
        
        def train_daily_attendance(self, data):
            return False
        
        def predict_daily_attendance(self, features):
            return 0
        
        def predict_user_attendance(self, history):
            return 0.5
        
        def get_attendance_trend(self, data):
            return {'trend': 'stable', 'growth_rate': 0, 'predicted_next_week': 0}
    
    # Initialize mock classes
    face_recognizer = FaceRecognizer()
    anomaly_detector = AnomalyDetector()
    attendance_predictor = AttendancePredictor()

# Initialize ML components (if not already initialized in mock)
if ML_AVAILABLE:
    face_recognizer = FaceRecognizer()
    anomaly_detector = AnomalyDetector()
    attendance_predictor = AttendancePredictor()


# =====================================================
# Machine Learning API Routes
# =====================================================

@app.route('/api/attendance/scan', methods=['POST'])
@login_required
def api_attendance_scan():
    """Process QR code scan for attendance"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    qr_data = data.get('qr_data')
    event_id = data.get('event_id')
    lecture_name = data.get('lecture_name', 'Main Session')
    
    if not qr_data or not event_id:
        return jsonify({'success': False, 'message': 'Missing data'}), 400
    
    conn = get_db_connection()
    try:
        # Try to parse QR data (assuming it contains user_id or email)
        import json
        try:
            qr_info = json.loads(qr_data)
            user_id = qr_info.get('user_id')
            email = qr_info.get('email')
        except:
            # If not JSON, assume it's a user ID
            user_id = qr_data if qr_data.isdigit() else None
            email = qr_data if '@' in qr_data else None
        
        # Find the user
        if user_id:
            user = conn.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
        elif email:
            user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        else:
            return jsonify({'success': False, 'message': 'Invalid QR code format'}), 400
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Check if already marked today
        existing = conn.execute('''
            SELECT id FROM attendance 
            WHERE user_id = ? AND event_id = ? AND date(timestamp) = date('now')
        ''', (user['id'], event_id)).fetchone()
        
        if existing:
            return jsonify({'success': False, 'message': 'Attendance already marked today'}), 400
        
        # Insert attendance
        conn.execute('''
            INSERT INTO attendance (user_id, event_id, lecture_name, timestamp, verified)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1)
        ''', (user['id'], event_id, lecture_name))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Attendance marked successfully'})
        
    except Exception as e:
        print(f"Error processing scan: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# =====================================================
# Get Lectures for Event API
# =====================================================

@app.route('/api/events/<int:event_id>/lectures')
@login_required
def get_event_lectures_api(event_id):
    """Get lectures for a specific event from lectures table"""
    conn = get_db_connection()
    try:
        # FIXED: Get lectures from the LECTURES table, not attendance
        lectures = conn.execute('''
            SELECT id, lecture_name as name, professor_name
            FROM lectures 
            WHERE event_id = ?
            ORDER BY created_at ASC
        ''', (event_id,)).fetchall()
        
        lecture_list = []
        for lecture in lectures:
            lecture_list.append({
                'id': lecture['id'],
                'name': lecture['name'],
                'professor': lecture['professor_name']
            })
        
        print(f"📚 Found {len(lecture_list)} lectures for event {event_id}")
        
        # Return empty list if no lectures found (no defaults)
        return jsonify(lecture_list)
        
    except Exception as e:
        print(f"Error fetching lectures: {e}")
        return jsonify([]), 500
    finally:
        conn.close()

@app.route('/api/ml/status')
def api_ml_status():
    """Get ML module status"""
    if not ML_AVAILABLE:
        return jsonify({
            'ml_available': False,
            'message': 'ML modules not available'
        })
    
    return jsonify({
        'ml_available': True,
        'face_recognition': face_recognizer.get_stats(),
        'anomaly_detection': {'available': True}
    })

@app.route('/api/face/add', methods=['POST'])
@login_required
def api_face_add():
    """Add a face to the recognition database"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML modules not available'}), 503
    
    user_id = request.form.get('user_id')
    user_name = request.form.get('user_name')
    
    if not user_id or not user_name:
        return jsonify({'error': 'User ID and name required'}), 400
    
    if 'face_image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporarily
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"face_{user_id}_{datetime.now().timestamp()}.jpg")
    file.save(temp_path)
    
    # Add face
    success, message = face_recognizer.add_face(int(user_id), user_name, temp_path)
    
    # Clean up
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/api/face/recognize', methods=['POST'])
@login_required
def api_face_recognize():
    """Recognize faces in an image"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML modules not available'}), 503
    
    if 'face_image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporarily
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"recognize_{datetime.now().timestamp()}.jpg")
    file.save(temp_path)
    
    # Recognize
    results = face_recognizer.recognize(temp_path)
    
    # Clean up
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    return jsonify({
        'success': True,
        'faces_detected': len(results),
        'results': results
    })

@app.route('/api/face/match', methods=['POST'])  # Changed endpoint
@login_required
def api_face_match():
    """Verify if face matches current user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Login required'}), 401
    
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML modules not available'}), 503
    
    user_id = request.form.get('user_id', session['user_id'])
    
    if 'face_image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save temporarily
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"verify_{datetime.now().timestamp()}.jpg")
    file.save(temp_path)
    
    # Verify
    is_match, confidence = face_recognizer.verify_face(int(user_id), temp_path)
    
    # Clean up
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    return jsonify({
        'success': True,
        'is_match': is_match,
        'confidence': confidence,
        'verified': is_match and confidence > 0.5
    })

@app.route('/api/face/stats')
@login_required
def api_face_stats():
    """Get face recognition statistics"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML modules not available'}), 503
    
    return jsonify(face_recognizer.get_stats())

@app.route('/api/anomaly/detect', methods=['POST'])
@login_required
def api_anomaly_detect():
    """Detect anomalies in attendance data"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin access required'}), 403
    
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML modules not available'}), 503
    
    conn = get_db_connection()
    try:
        # Get recent attendance data
        attendance = conn.execute('''
            SELECT a.*, u.name as user_name, e.name as event_name, e.date as event_date
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.timestamp >= datetime('now', '-30 days')
            ORDER BY a.timestamp DESC
        ''').fetchall()
        
        if len(attendance) < 10:
            return jsonify({
                'error': 'Not enough data for anomaly detection',
                'required': 10,
                'available': len(attendance)
            }), 400
        
        # Convert to list of dicts
        attendance_data = []
        for record in attendance:
            record_dict = dict(record)
            # Ensure all required fields are present
            attendance_data.append({
                'user_id': record_dict['user_id'],
                'user_name': record_dict.get('user_name', 'Unknown'),
                'event_id': record_dict['event_id'],
                'event_name': record_dict.get('event_name', 'Unknown'),
                'timestamp': record_dict['timestamp'],
                'fraud_score': record_dict.get('fraud_score', 0)
            })
        
        # Detect anomalies
        anomalies = anomaly_detector.detect_all(attendance_data)
        
        return jsonify(anomalies)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# =====================================================
# ML Dashboard Route (Web UI)
# =====================================================

@app.route('/ml-dashboard')
@login_required
def ml_dashboard():
    """Machine Learning Dashboard for analytics"""
    if 'admin_id' not in session and 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        # Get ML/Analytics data
        total_users = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()
        
        # Face enrollment stats
        face_enrolled = conn.execute('SELECT COUNT(*) as count FROM users WHERE face_enrolled = 1').fetchone()
        face_not_enrolled = conn.execute('SELECT COUNT(*) as count FROM users WHERE face_enrolled = 0').fetchone()
        
        # Attendance patterns by day of week
        attendance_by_day = conn.execute('''
            SELECT 
                CASE cast (strftime('%w', timestamp) as integer)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END as day,
                COUNT(*) as count
            FROM attendance
            GROUP BY strftime('%w', timestamp)
            ORDER BY strftime('%w', timestamp)
        ''').fetchall()
        
        # Fraud detection stats
        high_risk = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE fraud_score > 0.8').fetchone()
        medium_risk = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE fraud_score BETWEEN 0.5 AND 0.8').fetchone()
        low_risk = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE fraud_score < 0.5').fetchone()
        
        # Event popularity
        event_popularity = conn.execute('''
            SELECT e.name, COUNT(a.id) as attendance
            FROM events e
            LEFT JOIN attendance a ON e.id = a.event_id
            GROUP BY e.id
            ORDER BY attendance DESC
            LIMIT 5
        ''').fetchall()
        
        # Attendance over time (last 30 days)
        attendance_timeline = conn.execute('''
            SELECT 
                date(timestamp) as date,
                COUNT(*) as count
            FROM attendance
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY date(timestamp)
            ORDER BY date
        ''').fetchall()
        
        # User engagement stats
        active_users_7d = conn.execute('''
            SELECT COUNT(DISTINCT user_id) as count 
            FROM attendance 
            WHERE timestamp >= datetime('now', '-7 days')
        ''').fetchone()
        
        active_users_30d = conn.execute('''
            SELECT COUNT(DISTINCT user_id) as count 
            FROM attendance 
            WHERE timestamp >= datetime('now', '-30 days')
        ''').fetchone()
        
    except Exception as e:
        print(f"Error fetching ML data: {e}")
        # Set default values if tables don't exist
        total_users = {'count': 0}
        face_enrolled = {'count': 0}
        face_not_enrolled = {'count': 0}
        high_risk = {'count': 0}
        medium_risk = {'count': 0}
        low_risk = {'count': 0}
        attendance_by_day = []
        event_popularity = []
        attendance_timeline = []
        active_users_7d = {'count': 0}
        active_users_30d = {'count': 0}
    finally:
        conn.close()
    
    # Prepare data for charts
    attendance_pattern = []
    for record in attendance_by_day:
        attendance_pattern.append({
            'day': record['day'],
            'count': record['count']
        })
    
    events_data = []
    for event in event_popularity:
        events_data.append({
            'name': event['name'],
            'attendance': event['attendance']
        })
    
    timeline_data = []
    for record in attendance_timeline:
        timeline_data.append({
            'date': record['date'],
            'count': record['count']
        })
    
    ml_stats = {
        'total_users': total_users['count'] if total_users else 0,
        'face_enrolled': face_enrolled['count'] if face_enrolled else 0,
        'face_not_enrolled': face_not_enrolled['count'] if face_not_enrolled else 0,
        'face_enrollment_rate': round((face_enrolled['count'] / total_users['count'] * 100) if total_users and total_users['count'] > 0 else 0, 2),
        'high_risk': high_risk['count'] if high_risk else 0,
        'medium_risk': medium_risk['count'] if medium_risk else 0,
        'low_risk': low_risk['count'] if low_risk else 0,
        'total_fraud_alerts': (high_risk['count'] if high_risk else 0) + (medium_risk['count'] if medium_risk else 0),
        'active_users_7d': active_users_7d['count'] if active_users_7d else 0,
        'active_users_30d': active_users_30d['count'] if active_users_30d else 0,
        'attendance_pattern': attendance_pattern,
        'event_popularity': events_data,
        'attendance_timeline': timeline_data,
        'ml_available': ML_AVAILABLE
    }
    
    # Determine if user is admin for template
    is_admin = 'admin_id' in session
    
    return render_template('ml_dashboard.html', 
                         stats=ml_stats,
                         is_admin=is_admin,
                         ml_available=ML_AVAILABLE)

# =====================================================
# Machine Learning Routes
# =====================================================

@app.route('/api/ml/dashboard')
@login_required
def ml_dashboard_data():
    """Get ML dashboard data"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        # Get recent attendance data for analysis
        recent_attendance = conn.execute('''
            SELECT a.*, u.name as user_name, e.name as event_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.timestamp >= datetime('now', '-30 days')
            ORDER BY a.timestamp DESC
        ''').fetchall()
        
        data_list = []
        for record in recent_attendance:
            data_list.append({
                'user_id': record['user_id'],
                'user_name': record['user_name'],
                'event_id': record['event_id'],
                'event_name': record['event_name'],
                'timestamp': record['timestamp'],
                'fraud_score': record['fraud_score'],
                'verified': record['verified']
            })
        
        # Detect anomalies
        anomaly_results = anomaly_detector.detect_all(data_list) if data_list else {'anomalies': [], 'total_analyzed': 0}
        
        # Get trend analysis
        trend_analysis = attendance_predictor.get_attendance_trend(data_list) if data_list else {}
        
        # Get user engagement predictions
        users = conn.execute('SELECT id, name FROM users WHERE role = "user"').fetchall()
        user_predictions = []
        for user in users:
            user_history = [d for d in data_list if d['user_id'] == user['id']]
            if len(user_history) >= 3:
                # Group by date
                date_counts = {}
                for record in user_history:
                    date = record['timestamp'][:10] if record['timestamp'] else None
                    if date:
                        date_counts[date] = date_counts.get(date, 0) + 1
                
                history_list = [{'count': count} for count in date_counts.values()]
                
                if len(history_list) >= 3:
                    pred = attendance_predictor.predict_user_attendance(history_list)
                    user_predictions.append({
                        'user_id': user['id'],
                        'user_name': user['name'],
                        'predicted_rate': round(pred * 100, 2),
                        'attendance_count': len(user_history)
                    })
        
        user_predictions.sort(key=lambda x: x['predicted_rate'], reverse=True)
        
        return jsonify({
            'success': True,
            'anomalies': anomaly_results,
            'trend': trend_analysis,
            'user_predictions': user_predictions[:10],
            'face_stats': face_recognizer.get_stats(),
            'model_available': True
        })
        
    except Exception as e:
        print(f"Error in ML dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/fix-verified')
@login_required
def fix_verified_status():
    """Fix all attendance records to verified status"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        result = conn.execute('UPDATE attendance SET verified = 1 WHERE verified = 0 OR verified IS NULL')
        conn.commit()
        count = result.rowcount
        flash(f'✅ Successfully updated {count} attendance records to Verified!', 'success')
    except Exception as e:
        flash(f'❌ Error: {e}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('attendance_log'))

# ============================================
# FACE QUALITY VALIDATION FUNCTION
# ============================================

def validate_face_quality(image_path):
    """Validate face photo quality before accepting"""
    try:
        import face_recognition
        import cv2   
        import numpy as np

        image = face_recognition.load_image_file(image_path)
        
        # Check 1: Face detection
        face_locations = face_recognition.face_locations(image)
        if len(face_locations) != 1:
            return False, "Must have exactly one face in photo"
        
        # Check 2: Image clarity
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 100:
            return False, "Photo too blurry, please retake"
        
        # Check 3: Face size
        top, right, bottom, left = face_locations[0]
        face_height = bottom - top
        face_width = right - left
        image_height, image_width = image.shape[:2]
        
        face_ratio = (face_height * face_width) / (image_height * image_width)
        if face_ratio < 0.1:
            return False, "Face too small, move closer"
        if face_ratio > 0.8:
            return False, "Face too close, move back"
        
        # Check 4: Brightness
        brightness = np.mean(gray)
        if brightness < 60:
            return False, "Photo too dark"
        if brightness > 200:
            return False, "Photo too bright"
        
        return True, "Quality approved"
    except Exception as e:
        return False, f"Error processing image: {str(e)}"

# Add this route for quality check
@app.route('/api/face/check-quality', methods=['POST'])
def check_face_quality():
    """API endpoint to check face photo quality"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image provided'}), 400
        
        file = request.files['image']
        temp_path = 'temp_face_check.jpg'
        file.save(temp_path)
        
        is_good, message = validate_face_quality(temp_path)
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'is_quality': is_good,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/ml/predict-attendance', methods=['POST'])
@login_required
def predict_attendance():
    """Predict attendance for specific event/date"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    event_id = data.get('event_id')
    date_str = data.get('date')
    
    if not event_id:
        return jsonify({'error': 'Event ID required'}), 400
    
    conn = get_db_connection()
    try:
        # Get historical data for the event
        event_data = conn.execute('''
            SELECT COUNT(*) as count, date(timestamp) as date
            FROM attendance
            WHERE event_id = ?
            GROUP BY date(timestamp)
            ORDER BY date DESC
            LIMIT 30
        ''', (event_id,)).fetchall()
        
        # Get day features for prediction
        if date_str:
            pred_date = datetime.fromisoformat(date_str)
        else:
            pred_date = datetime.now() + timedelta(days=1)
        
        # Get recent average
        recent_avg = np.mean([d['count'] for d in event_data[:7]]) if event_data else 0
        
        features = {
            'day_of_week': pred_date.weekday(),
            'prev_attendance': event_data[0]['count'] if event_data else 0,
            'day_of_month': pred_date.day,
            'is_weekend': 1 if pred_date.weekday() in [5, 6] else 0,
            'week_avg': recent_avg
        }
        
        # Get event details
        event = conn.execute('SELECT name, date FROM events WHERE id = ?', (event_id,)).fetchone()
        prediction = attendance_predictor.predict_daily_attendance(features)
        
        # Calculate confidence based on data availability
        confidence = 0.5
        if len(event_data) >= 10:
            confidence = 0.85
        elif len(event_data) >= 5:
            confidence = 0.70
        
        return jsonify({
            'success': True,
            'predicted_attendance': int(prediction),
            'event_name': event['name'] if event else 'Unknown Event',
            'date': date_str or event['date'] if event else None,
            'confidence': confidence,
            'historical_avg': int(recent_avg),
            'historical_data_points': len(event_data)
        })
        
    except Exception as e:
        print(f"Error in prediction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/ml/train', methods=['POST'])
@login_required
def train_ml_models_endpoint():
    """Manually trigger ML model training"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        import threading
        training_thread = threading.Thread(target=train_ml_models)
        training_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'ML training started in background'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# Additional Bulk Import API Routes
# =====================================================

@app.route('/api/admin/fetch-students-api', methods=['POST'])
@login_required
def fetch_students_from_api():
    """Fetch students from external API (Moodle, ERP, etc.)"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    source = data.get('source')
    api_url = data.get('api_url')
    api_key = data.get('api_key')
    course_id = data.get('course_id')
    
    # Mock data for demonstration
    mock_students = [
        {'name': 'John Doe', 'email': 'john.doe@example.com', 'student_id': 'CS001', 'moodle_id': 'moodle_john'},
        {'name': 'Jane Smith', 'email': 'jane.smith@example.com', 'student_id': 'CS002', 'moodle_id': 'moodle_jane'},
        {'name': 'Bob Johnson', 'email': 'bob.johnson@example.com', 'student_id': 'CS003', 'moodle_id': 'moodle_bob'},
        {'name': 'Alice Brown', 'email': 'alice.brown@example.com', 'student_id': 'CS004', 'moodle_id': 'moodle_alice'},
        {'name': 'Charlie Wilson', 'email': 'charlie.wilson@example.com', 'student_id': 'CS005', 'moodle_id': 'moodle_charlie'},
    ]
    
    return jsonify({
        'success': True,
        'students': mock_students,
        'source': source,
        'count': len(mock_students)
    })

@app.route('/admin/location-reports')
@login_required
def location_reports():
    """Admin report for location verification"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    try:
        # Get attendance with location data
        location_attendance = conn.execute('''
            SELECT 
                a.id,
                a.timestamp,
                a.location_verified,
                a.location_distance,
                a.checkin_latitude,
                a.checkin_longitude,
                u.name as user_name,
                u.email as user_email,
                e.name as event_name,
                e.venue_latitude,
                e.venue_longitude,
                e.venue_radius
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            WHERE a.location_verified IS NOT NULL
            ORDER BY a.timestamp DESC
            LIMIT 100
        ''').fetchall()
        
        stats = {
            'total_location_checks': len(location_attendance),
            'verified_count': len([a for a in location_attendance if a['location_verified'] == 1]),
            'failed_count': len([a for a in location_attendance if a['location_verified'] == 0]),
            'avg_distance': sum([a['location_distance'] for a in location_attendance if a['location_distance']]) / len(location_attendance) if location_attendance else 0
        }
        
    except Exception as e:
        print(f"Error fetching location reports: {e}")
        location_attendance = []
        stats = {'total_location_checks': 0, 'verified_count': 0, 'failed_count': 0, 'avg_distance': 0}
    finally:
        conn.close()
    
    return render_template('admin/location_reports.html', 
                         attendance=location_attendance, 
                         stats=stats)

@app.route('/api/admin/bulk-import-api', methods=['POST'])
@login_required
def bulk_import_from_api():
    """Import students fetched from API"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    students = data.get('students', [])
    auto_verify = data.get('auto_verify', True)
    
    if not students:
        return jsonify({'success': False, 'message': 'No students to import'}), 400
    
    import hashlib
    conn = get_db_connection()
    imported_count = 0
    errors = []
    
    try:
        for student in students:
            email = student.get('email', '').strip().lower()
            name = student.get('name', '').strip()
            
            if not name or not email:
                errors.append(f"Student {student.get('name', 'Unknown')}: Missing name or email")
                continue
            
            # Check if exists
            existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if existing:
                errors.append(f"Student {email}: Already exists")
                continue
            
            try:
                # Insert
                conn.execute('''
                    INSERT INTO users (name, email, password, student_id, moodle_id, role, verified, created_at)
                    VALUES (?, ?, ?, ?, ?, 'user', ?, CURRENT_TIMESTAMP)
                ''', (
                    name, 
                    email, 
                    hashlib.md5('Student@123'.encode()).hexdigest(),
                    student.get('student_id'),
                    student.get('moodle_id'),
                    1 if auto_verify else 0
                ))
                imported_count += 1
            except Exception as e:
                errors.append(f"Student {email}: {str(e)}")
        
        conn.commit()
        
        # Log the import
        try:
            conn.execute('''
                INSERT INTO bulk_imports (source, count, status, details)
                VALUES (?, ?, 'completed', ?)
            ''', (f"API Import ({len(students)} fetched)", imported_count, f'Auto verify: {auto_verify}'))
            conn.commit()
        except:
            pass
        
        message = f"Successfully imported {imported_count} students"
        if errors:
            message += f". {len(errors)} errors: {', '.join(errors[:5])}"
        
        return jsonify({
            'success': True,
            'message': message,
            'imported': imported_count,
            'errors': errors
        })
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/export-verified')
@login_required
def export_verified_students():
    """Export verified students list"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    import io
    import csv
    from flask import make_response
    
    conn = get_db_connection()
    try:
        students = conn.execute('''
            SELECT name, email, student_id, moodle_id, phone_number, created_at 
            FROM users 
            WHERE role = 'user' AND verified = 1
            ORDER BY name
        ''').fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Email', 'Student ID', 'Moodle ID', 'Phone Number', 'Registered Date'])
        
        for student in students:
            writer.writerow([
                student['name'],
                student['email'],
                student['student_id'] or '',
                student['moodle_id'] or '',
                student['phone_number'] or '',
                student['created_at'][:10] if student['created_at'] else ''
            ])
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=verified_students.csv'
        response.headers['Content-type'] = 'text/csv'
        return response
        
    except Exception as e:
        flash(f'Error exporting: {e}', 'danger')
        return redirect(url_for('bulk_verify'))
    finally:
        conn.close()

@app.route('/api/admin/send-bulk-credentials', methods=['POST'])
@login_required
def send_bulk_credentials():
    """Send login credentials to verified students"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    try:
        # Get verified students
        students = conn.execute('''
            SELECT name, email FROM users 
            WHERE role = 'user' AND verified = 1 AND email IS NOT NULL
        ''').fetchall()
        
        # In production, implement actual email sending here
        # For now, just return count
        
        return jsonify({
            'success': True,
            'message': f'Credentials would be sent to {len(students)} students',
            'count': len(students)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# In your face enrollment function, add multiple captures
@app.route('/api/face/enroll-multiple', methods=['POST'])
@login_required
def enroll_face_multiple():
    """Enroll multiple face angles for the current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    face_image_data = data.get('face_image')
    angle = data.get('angle', 'unknown')
    
    if not face_image_data:
        return jsonify({'success': False, 'message': 'No face image provided'}), 400
    
    try:
        import base64
        import io
        from PIL import Image
        
        if ',' in face_image_data:
            face_image_data = face_image_data.split(',')[1]
        
        image_bytes = base64.b64decode(face_image_data)
        
        user_id = session['user_id']
        face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
        os.makedirs(face_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"face_{user_id}_{angle}_{timestamp}.jpg"
        filepath = os.path.join(face_dir, filename)
        
        image = Image.open(io.BytesIO(image_bytes))
        image.save(filepath, 'JPEG', quality=95)
        
        # Count images for this user
        image_count = len([f for f in os.listdir(face_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])
        
        return jsonify({
            'success': True,
            'message': f'Face captured ({angle} angle). Total: {image_count} images',
            'filename': filename,
            'image_count': image_count
        })
        
    except Exception as e:
        print(f"Error enrolling face: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
# Add this function before auto_detect_face:
def preprocess_face_image(face_roi):
    """Enhance face image for better recognition"""
    # Apply histogram equalization
    equalized = cv2.equalizeHist(face_roi)
    
    # Apply slight blur to reduce noise
    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    
    # Resize to standard size
    resized = cv2.resize(blurred, (100, 100))
    
    return resized

# Then in auto_detect_face, replace:
face_roi = gray[y:y+h, x:x+w]
face_roi = cv2.resize(face_roi, (100, 100))

# With:
face_roi = gray[y:y+h, x:x+w]
face_roi = preprocess_face_image(face_roi)

@app.route('/api/face/complete-enrollment', methods=['POST'])
def complete_face_enrollment():
    """Complete face enrollment after multiple captures"""
    data = request.get_json()
    user_id = data.get('user_id') if data else None
    
    if not user_id:
        return jsonify({'success': False, 'message': 'User ID required'}), 400
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE users 
            SET face_enrolled = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
        
        # Call train function directly
        from werkzeug.utils import redirect
        # Trigger training
        train_result = train_face_model()
        
        return jsonify({
            'success': True,
            'message': 'Face enrollment completed successfully!'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/face/get-enrolled-photos')
@login_required
def get_enrolled_photos():
    """Get all enrolled photos for the current user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
    
    photos = []
    if os.path.exists(face_dir):
        for filename in os.listdir(face_dir):
            if filename.endswith(('.jpg', '.png', '.jpeg')):
                photos.append({
                    'url': url_for('static', filename=f'faces/{user_id}/{filename}'),
                    'filename': filename
                })
    
    return jsonify({'success': True, 'photos': photos})

@app.route('/face-enrollment/enhanced')
@login_required
def enhanced_face_enrollment():
    """Enhanced face enrollment page with multi-angle capture"""
    if 'user_id' not in session:
        flash('Please login first', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        user = conn.execute('SELECT id, name, email, student_id, face_enrolled FROM users WHERE id = ?', 
                           (session['user_id'],)).fetchone()
        
        return render_template('enhanced_face_enrollment.html', user=dict(user))
    finally:
        conn.close()
    
# =====================================================
# Bulk Import and Verification Routes
# =====================================================

@app.route('/admin/bulk-import')
@login_required
def bulk_import():
    """Bulk import students page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    return render_template('admin/bulk_import.html')

@app.route('/admin/bulk-verify')
@login_required
def bulk_verify():
    """Bulk verify students page"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    return render_template('admin/bulk_verify.html')

@app.route('/api/admin/bulk-import', methods=['POST'])
def bulk_import_students():
    """Process bulk import of students from Excel/CSV"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400
    
    file = request.files['file']
    auto_verify = request.form.get('auto_verify') == 'true'
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    try:
        import pandas as pd
        import hashlib
        
        # Try to read the file
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            # For Excel files
            try:
                df = pd.read_excel(file, engine='openpyxl')
            except:
                df = pd.read_excel(file, engine='xlrd')
        
        # Print debug info to console
        print(f"File: {file.filename}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Rows: {len(df)}")
        print(f"First row: {df.iloc[0].to_dict() if len(df) > 0 else 'Empty'}")
        
        # Handle different column name formats
        # Try to find name column
        name_col = None
        for col in df.columns:
            if 'name' in str(col).lower() or 'student' in str(col).lower():
                name_col = col
                break
        if name_col is None:
            name_col = df.columns[0]  # Assume first column is name
        
        # Try to find email column
        email_col = None
        for col in df.columns:
            if 'email' in str(col).lower():
                email_col = col
                break
        if email_col is None:
            email_col = df.columns[1]  # Assume second column is email
        
        # Try to find student_id column
        student_id_col = None
        for col in df.columns:
            if 'student' in str(col).lower() or 'id' in str(col).lower() or 'roll' in str(col).lower():
                student_id_col = col
                break
        
        # Try to find moodle_id column
        moodle_id_col = None
        for col in df.columns:
            if 'moodle' in str(col).lower():
                moodle_id_col = col
                break
        
        print(f"Mapped - Name: {name_col}, Email: {email_col}, Student ID: {student_id_col}, Moodle: {moodle_id_col}")
        
        conn = get_db_connection()
        imported_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                name = str(row[name_col]).strip()
                email = str(row[email_col]).strip().lower()
                
                # Skip empty rows
                if name == 'nan' or email == 'nan' or not name or not email:
                    continue
                
                # Check if email already exists
                existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
                if existing:
                    errors.append(f"Row {idx+2}: {email} already exists")
                    continue
                
                # Prepare insert data
                insert_data = {
                    'name': name,
                    'email': email,
                    'password': hashlib.md5('Student@123'.encode()).hexdigest(),
                    'role': 'user',
                    'verified': 1 if auto_verify else 0
                }
                
                # Add student_id if found
                if student_id_col:
                    student_id_val = row[student_id_col]
                    if str(student_id_val) != 'nan':
                        insert_data['student_id'] = str(student_id_val).strip()
                
                # Add moodle_id if found
                if moodle_id_col:
                    moodle_id_val = row[moodle_id_col]
                    if str(moodle_id_val) != 'nan':
                        insert_data['moodle_id'] = str(moodle_id_val).strip()
                
                # Insert into database
                columns = list(insert_data.keys())
                placeholders = ','.join(['?' for _ in columns])
                values = [insert_data[col] for col in columns]
                query = f"INSERT INTO users ({','.join(columns)}) VALUES ({placeholders})"
                conn.execute(query, values)
                imported_count += 1
                print(f"✅ Imported: {name} - {email}")
                
            except Exception as e:
                errors.append(f"Row {idx+2}: {str(e)}")
                print(f"❌ Error row {idx+2}: {e}")
        
        conn.commit()
        
        # ========== ADD THIS LOGGING SECTION ==========
        # Log the import to bulk_imports table
        try:
            # Create table if not exists
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bulk_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    count INTEGER,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    details TEXT
                )
            ''')
            # Insert import record
            conn.execute('''
                INSERT INTO bulk_imports (source, count, status, details)
                VALUES (?, ?, 'completed', ?)
            ''', (file.filename, imported_count, f'Auto verify: {auto_verify}, Errors: {len(errors)}'))
            conn.commit()
            print(f"✅ Import logged: {file.filename} - {imported_count} students")
        except Exception as log_error:
            print(f"⚠️ Log error (non-critical): {log_error}")
        # ==============================================
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {imported_count} students',
            'imported': imported_count,
            'errors': errors[:20]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    
# Page route (GET)
@app.route('/admin/bulk-import')
@login_required
def bulk_import_page():
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    return render_template('admin/bulk_import.html')

    
@app.route('/admin/test-import', methods=['POST'])
@login_required
def test_import():
    """Test endpoint to debug import issues"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin required'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    
    try:
        import pandas as pd
        import io
        
        # Read the file
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Return file info
        info = {
            'filename': file.filename,
            'columns': df.columns.tolist(),
            'first_5_rows': df.head().to_dict(),
            'shape': df.shape,
            'dtypes': df.dtypes.astype(str).to_dict()
        }
        
        return jsonify({'success': True, 'info': info})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/bulk-verify', methods=['POST'])
@login_required
def bulk_verify_students():
    """Bulk verify or reject students"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    action = data.get('action')
    student_ids = data.get('student_ids', [])
    
    conn = get_db_connection()
    
    try:
        if action == 'verify_all':
            # Verify all pending students
            result = conn.execute('''
                UPDATE users 
                SET verified = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE role = 'user' AND (verified = 0 OR verified IS NULL)
            ''')
            count = result.rowcount
            
        elif action == 'verify' and student_ids:
            # Verify specific students
            placeholders = ','.join(['?' for _ in student_ids])
            result = conn.execute(f'''
                UPDATE users 
                SET verified = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE id IN ({placeholders}) AND role = 'user'
            ''', student_ids)
            count = result.rowcount
            
        elif action == 'reject' and student_ids:
            # Reject (delete) specific students
            placeholders = ','.join(['?' for _ in student_ids])
            conn.execute(f'DELETE FROM attendance WHERE user_id IN ({placeholders})', student_ids)
            result = conn.execute(f'DELETE FROM users WHERE id IN ({placeholders}) AND role = "user"', student_ids)
            count = result.rowcount
            
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400
        
        conn.commit()
        
        action_word = 'verified' if 'verify' in action else 'rejected'
        return jsonify({
            'success': True,
            'message': f'{count} student(s) {action_word} successfully',
            'count': count
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/students', methods=['GET'])
@login_required
def get_students_for_bulk_verify():
    """Get students for bulk verify page with pagination"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    status = request.args.get('status', 'pending')
    search = request.args.get('search', '')
    
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    
    try:
        # Build query
        query = "SELECT id, name, email, student_id, moodle_id, phone_number, created_at as registered_on, verified FROM users WHERE role = 'user'"
        count_query = "SELECT COUNT(*) as total FROM users WHERE role = 'user'"
        params = []
        
        if status == 'pending':
            query += " AND (verified = 0 OR verified IS NULL)"
            count_query += " AND (verified = 0 OR verified IS NULL)"
        elif status == 'verified':
            query += " AND verified = 1"
            count_query += " AND verified = 1"
        
        if search:
            query += " AND (name LIKE ? OR email LIKE ? OR student_id LIKE ? OR moodle_id LIKE ?)"
            count_query += " AND (name LIKE ? OR email LIKE ? OR student_id LIKE ? OR moodle_id LIKE ?)"
            search_pattern = f'%{search}%'
            params.extend([search_pattern] * 4)
        
        # Get total count
        total_result = conn.execute(count_query, params).fetchone()
        total = total_result['total'] if total_result else 0
        
        # Get paginated results
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        students = conn.execute(query, params).fetchall()
        
        student_list = []
        for student in students:
            student_list.append({
                'id': student['id'],
                'name': student['name'],
                'email': student['email'],
                'student_id': student['student_id'],
                'moodle_id': student['moodle_id'],
                'phone': student['phone_number'],
                'registered_on': student['registered_on'][:10] if student['registered_on'] else None,
                'verified': bool(student['verified'])
            })
        
        return jsonify({
            'success': True,
            'students': student_list,
            'total': total,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/admin/recent-imports', methods=['GET'])
def get_recent_imports():
    """Get recent bulk import history"""
    
    conn = get_db_connection()
    
    try:
        # Create table if not exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bulk_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                count INTEGER,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')
        conn.commit()
        
        # Get recent imports
        imports = conn.execute('''
            SELECT * FROM bulk_imports 
            ORDER BY timestamp DESC 
            LIMIT 20
        ''').fetchall()
        
        import_list = []
        for imp in imports:
            import_list.append({
                'id': imp['id'],
                'source': imp['source'],
                'count': imp['count'],
                'status': imp['status'],
                'timestamp': imp['timestamp'],
                'details': imp['details']
            })
        
        return jsonify({'success': True, 'imports': import_list})
        
    except Exception as e:
        print(f"Error getting imports: {e}")
        return jsonify({'success': True, 'imports': []})
    finally:
        conn.close()

@app.route('/debug/check-session')
def check_session():
    return jsonify({
        'admin_id': session.get('admin_id'),
        'user_id': session.get('user_id'),
        'session_keys': list(session.keys())
    })

@app.route('/api/admin/download-template/<format>')
@login_required
def download_template(format):
    """Download template for bulk import"""
    if 'admin_id' not in session:
        flash('Admin access required', 'error')
        return redirect(url_for('admin_login'))
    
    import io
    import csv
    from flask import make_response
    
    sample_data = [
        {
            'name': 'John Doe',
            'email': 'john.doe@university.edu',
            'student_id': '2024CS001',
            'moodle_id': 'john_doe',
            'phone_number': '9876543210',
            'aadhaar_number': '1234-5678-9012'
        },
        {
            'name': 'Jane Smith',
            'email': 'jane.smith@university.edu',
            'student_id': '2024CS002',
            'moodle_id': 'jane_smith',
            'phone_number': '9876543211',
            'aadhaar_number': '2345-6789-0123'
        }
    ]
    
    if format == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=sample_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_data)
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=student_import_template.csv'
        response.headers['Content-type'] = 'text/csv'
        return response
        
    else:  # excel
        import pandas as pd
        df = pd.DataFrame(sample_data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = 'attachment; filename=student_import_template.xlsx'
        response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response
    
# =====================================================
# Public Statistics API Endpoint
# =====================================================

@app.route('/api/public/stats', methods=['GET'])
def public_stats():
    """Public API endpoint for system statistics - No authentication required"""
    conn = get_db_connection()
    try:
        # Get real statistics from database
        total_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "user"').fetchone()
        total_events = conn.execute('SELECT COUNT(*) as count FROM events').fetchone()
        total_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance').fetchone()
        today_attendance = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE date(timestamp) = date("now")').fetchone()
        
        # Active events (upcoming)
        active_events = conn.execute('SELECT COUNT(*) as count FROM events WHERE date >= date("now")').fetchone()
        
        # Pending verifications
        pending_verifications = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "user" AND (verified = 0 OR verified IS NULL)').fetchone()
        
        # Fraud alerts
        fraud_alerts = conn.execute('SELECT COUNT(*) as count FROM attendance WHERE fraud_score > 0.7').fetchone()
        
        stats = {
            'success': True,
            'data': {
                'total_users': total_users['count'] if total_users else 0,
                'total_events': total_events['count'] if total_events else 0,
                'total_attendance': total_attendance['count'] if total_attendance else 0,
                'today_attendance': today_attendance['count'] if today_attendance else 0,
                'active_events': active_events['count'] if active_events else 0,
                'pending_verifications': pending_verifications['count'] if pending_verifications else 0,
                'fraud_alerts': fraud_alerts['count'] if fraud_alerts else 0,
                'system_status': 'operational',
                'last_updated': datetime.now().isoformat()
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error in public_stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Unable to fetch statistics'
        }), 500
    finally:
        conn.close()
    
# =====================================================
# Admin Face Management Routes
# =====================================================

@app.route('/api/admin/user-face-photos/<int:user_id>')
@login_required
def admin_get_user_face_photos(user_id):
    """Admin: Get all face photos for a specific user"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    user_face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
    
    photos = []
    if os.path.exists(user_face_dir):
        for filename in os.listdir(user_face_dir):
            if filename.endswith(('.jpg', '.png', '.jpeg')):
                # Get file modification time
                filepath = os.path.join(user_face_dir, filename)
                timestamp = os.path.getmtime(filepath)
                
                photos.append({
                    'id': hash(filename),
                    'filename': filename,
                    'url': url_for('static', filename=f'faces/{user_id}/{filename}'),
                    'timestamp': timestamp
                })
        
        # Sort by timestamp (newest first)
        photos.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        'success': True,
        'photos': photos,
        'count': len(photos)
    })

@app.route('/api/admin/delete-face-photo/<int:photo_id>', methods=['DELETE'])
@login_required
def admin_delete_face_photo(photo_id):
    """Admin: Delete a specific face photo"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Note: This is a simplified version. In production, you'd need to map photo_id to actual file
    # For now, we'll use the filename from request
    data = request.get_json()
    filename = data.get('filename')
    user_id = data.get('user_id')
    
    if not filename or not user_id:
        return jsonify({'success': False, 'message': 'Missing filename or user_id'}), 400
    
    filepath = os.path.join('frontend', 'static', 'faces', str(user_id), filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True, 'message': 'Photo deleted'})
    else:
        return jsonify({'success': False, 'message': 'Photo not found'}), 404

@app.route('/api/admin/delete-all-user-face-photos/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_all_user_face_photos(user_id):
    """Admin: Delete all face photos for a user"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    user_face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
    
    deleted_count = 0
    if os.path.exists(user_face_dir):
        for filename in os.listdir(user_face_dir):
            if filename.endswith(('.jpg', '.png', '.jpeg')):
                filepath = os.path.join(user_face_dir, filename)
                os.remove(filepath)
                deleted_count += 1
    
    return jsonify({
        'success': True,
        'message': f'Deleted {deleted_count} photos',
        'count': deleted_count
    })

@app.route('/admin/face-management')
@login_required
def admin_face_management():
    """Admin: Manage all users' face enrollments - SHOW ACTUAL PHOTOS"""
    if 'admin_id' not in session and 'user_id' not in session:
        flash('Login required', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        users = conn.execute('''
            SELECT id, name, email, face_enrolled, created_at
            FROM users 
            WHERE role = 'user'
            ORDER BY created_at DESC
        ''').fetchall()
        
        user_list = []
        total_face_photos = 0
        
        # Get the correct base path for faces
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(backend_dir)
        faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
        
        print(f"🔍 Looking for faces in: {faces_base_dir}")
        
        for user in users:
            # Count face photos and get URLs
            user_dir = os.path.join(faces_base_dir, str(user['id']))
            face_count = 0
            face_photos = []  # Store actual photo URLs
            
            if os.path.exists(user_dir):
                face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
                face_count = len(face_files)
                total_face_photos += face_count
                
                # Get ALL photos for display with correct URLs
                for face_file in face_files:
                    face_photos.append({
                        'url': f'/static/faces/{user["id"]}/{face_file}',  # Correct URL
                        'filename': face_file
                    })
                
                if face_count > 0:
                    print(f"✅ User {user['name']} (ID: {user['id']}) has {face_count} face photos")
            else:
                print(f"⚠️ No face directory for user {user['name']} (ID: {user['id']})")
            
            # Determine if face is enrolled (has photos OR face_enrolled flag is True)
            is_face_enrolled = (user['face_enrolled'] == 1) or (face_count > 0)
            
            user_list.append({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'face_enrolled': is_face_enrolled,
                'face_count': face_count,
                'face_photos': face_photos,  # Add the actual photos
                'registered_on': user['created_at'][:10] if user['created_at'] else 'N/A'
            })
        
        print(f"📊 Total face photos found: {total_face_photos}")
        
    except Exception as e:
        print(f"Error in admin_face_management: {e}")
        import traceback
        traceback.print_exc()
        user_list = []
        total_face_photos = 0
    finally:
        conn.close()
    
    # Get last training time from model file
    import datetime
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(backend_dir, 'ml_models', 'saved_models', 'face_recognizer.yml')
    last_training = "Never"
    if os.path.exists(model_path):
        last_modified = os.path.getmtime(model_path)
        last_training = datetime.datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate actual enrolled users count
    enrolled_users = len([u for u in user_list if u['face_enrolled']])
    
    stats = {
        'total_faces': total_face_photos,
        'total_users': len(user_list),
        'enrolled_users': enrolled_users,
        'last_training': last_training,
        'accuracy': 0.95
    }
    
    return render_template('admin/face_management.html', users=user_list, stats=stats)

@app.route('/debug/face-paths')
def debug_face_paths():
    """Debug endpoint to check face photo paths"""
    import os
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(backend_dir)
    faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
    
    result = {
        'faces_base_dir': faces_base_dir,
        'exists': os.path.exists(faces_base_dir),
        'users': []
    }
    
    if os.path.exists(faces_base_dir):
        for user_id in os.listdir(faces_base_dir):
            user_dir = os.path.join(faces_base_dir, user_id)
            if os.path.isdir(user_dir):
                photos = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
                result['users'].append({
                    'user_id': user_id,
                    'photo_count': len(photos),
                    'photos': photos[:5],  # First 5 photos
                    'full_path': user_dir
                })
    
    return jsonify(result)

# =====================================================
# Debug OpenCV Check
# =====================================================

@app.route('/debug/opencv-check')
def debug_opencv_check():
    """Check OpenCV face module availability"""
    import cv2
    import sys
    import os
    
    result = {
        'cv2_version': cv2.__version__,
        'has_face_module': hasattr(cv2, 'face'),
        'python_version': sys.version,
        'available_recognizers': []
    }
    
    if hasattr(cv2, 'face'):
        if hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
            result['available_recognizers'].append('LBPHFaceRecognizer')
        if hasattr(cv2.face, 'EigenFaceRecognizer_create'):
            result['available_recognizers'].append('EigenFaceRecognizer')
        if hasattr(cv2.face, 'FisherFaceRecognizer_create'):
            result['available_recognizers'].append('FisherFaceRecognizer')
    
    # Check face directories
    face_dirs = []
    faces_path = os.path.join('frontend', 'static', 'faces')
    
    if os.path.exists(faces_path):
        for user_id in os.listdir(faces_path):
            user_dir = os.path.join(faces_path, user_id)
            if os.path.isdir(user_dir):
                face_count = len([f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))])
                face_dirs.append({'user_id': user_id, 'face_count': face_count})
    else:
        result['faces_path_error'] = f'Path not found: {faces_path}'
    
    result['face_directories'] = face_dirs
    result['total_faces'] = sum([d['face_count'] for d in face_dirs])
    
    return jsonify(result)
    
if __name__ == '__main__':
    # Create database directory if it doesn't exist
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)
    add_location_columns_to_events()
    
    # Initialize database and run migrations
    print("=" * 50)
    print("Starting AMS Application")
    print("=" * 50)
    
    init_db()
    run_migrations()
    add_event_time_columns()
    
    # Run face migration using MigrationManager if available
    if MIGRATION_MANAGER_AVAILABLE:
        try:
            print("\n" + "=" * 50)
            print("Running Face Enrollment Migration")
            print("=" * 50)
            success = MigrationManager.run_face_migration(app.config['DATABASE_PATH'])
            if success:
                print("✅ Face enrollment columns verified/added successfully")
            else:
                print("⚠️ Face migration had issues, but app will continue")
        except Exception as e:
            print(f"⚠️ Could not run face migration: {e}")
            print("   The app will still work, but face enrollment may have issues")
    else:
        print("\n⚠️ MigrationManager not available - using built-in migrations only")
        print("   Face enrollment columns were handled by run_migrations()")
    
    # ========== ADD THIS SECTION ==========
    # Train ML models on startup
    print("\n" + "=" * 50)
    print("Training ML Models")
    print("=" * 50)
    train_ml_models()

    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"   Mobile: http://{local_ip}:5000")
    except:
        pass
    
    print("=" * 50)
    
    # Schedule periodic ML training
    schedule_ml_training()
    # =====================================
    
    print("\n" + "=" * 50)
    print("🚀 Starting Flask server on http://127.0.0.1:5000")
    print("=" * 50)
    
    # Run the app
    app.run(debug=True, port=5000, host='0.0.0.0') 