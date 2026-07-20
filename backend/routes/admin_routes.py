from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session
import sqlite3
import os
from functools import wraps

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """Create a database connection"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                          'database', 'event_system.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@admin_bp.route('/users')
@admin_required
def manage_users():
    """Manage users page"""
    conn = get_db_connection()
    try:
        users = conn.execute('''
            SELECT id, name, email, role, verified, face_enrolled, created_at
            FROM users ORDER BY created_at DESC
        ''').fetchall()
        
        user_list = []
        for user in users:
            user_list.append({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role'],
                'verified': '✅' if user['verified'] else '❌',
                'face_enrolled': '✅' if user['face_enrolled'] else '❌',
                'created_at': user['created_at'][:10] if user['created_at'] else 'N/A'
            })
    except Exception as e:
        print(f"Error: {e}")
        user_list = []
    finally:
        conn.close()
    
    return render_template('admin/manage_users.html', users=user_list)

@admin_bp.route('/events')
@admin_required
def manage_events():
    """Manage events page"""
    conn = get_db_connection()
    try:
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
        print(f"Error: {e}")
        event_list = []
    finally:
        conn.close()
    
    return render_template('admin/manage_events.html', events=event_list)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard"""
    return redirect(url_for('admin_dashboard'))

@admin_bp.route('/verifications')
@admin_required
def verifications():
    """Pending verifications page"""
    conn = get_db_connection()
    try:
        pending = conn.execute('''
            SELECT id, name, email, phone_number, moodle_id, aadhaar_number, student_id, created_at
            FROM users WHERE role = 'user' AND (verified = 0 OR verified IS NULL)
            ORDER BY created_at DESC
        ''').fetchall()
        
        pending_list = []
        for user in pending:
            pending_list.append({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'phone': user['phone_number'] or 'N/A',
                'moodle_id': user['moodle_id'] or 'N/A',
                'aadhaar': user['aadhaar_number'] or 'N/A',
                'student_id': user['student_id'] or 'N/A',
                'registered_on': user['created_at'][:10] if user['created_at'] else 'N/A'
            })
    except Exception as e:
        print(f"Error: {e}")
        pending_list = []
    finally:
        conn.close()
    
    return render_template('admin/verifications.html', pending_users=pending_list)

@admin_bp.route('/settings')
@admin_required
def settings():
    """Admin settings page"""
    return render_template('admin/settings.html')