"""
Admin routes for dashboard and management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime

from backend.models.user import User
from backend.models.admin import Admin
from backend.models.event import Event
from backend.models.lecture import Lecture
from backend.models.verification import Verification
from backend.utils.database import get_db
from backend.utils.security import admin_required
from backend.utils.audit import log_audit
from backend.utils.validators import sanitize_input

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard"""
    db = get_db()
    
    # Get statistics
    stats = db.execute('''
        SELECT 
            (SELECT COUNT(*) FROM users WHERE is_active = 1) as active_users,
            (SELECT COUNT(*) FROM events WHERE is_active = 1) as active_events,
            (SELECT COUNT(*) FROM lectures WHERE is_active = 1) as active_lectures,
            (SELECT COUNT(*) FROM attendance WHERE DATE(timestamp) = DATE('now')) as today_attendance,
            (SELECT COUNT(*) FROM id_verification WHERE status = 'PENDING') as pending_verifications,
            (SELECT AVG(fraud_score) FROM attendance WHERE DATE(timestamp) = DATE('now')) as avg_fraud_score
    ''').fetchone()
    
    # Get recent attendance
    recent_attendance = db.execute('''
        SELECT a.*, u.name as user_name, e.name as event_name, l.subject as lecture_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        ORDER BY a.timestamp DESC
        LIMIT 10
    ''').fetchall()
    
    # Get recent fraud alerts
    fraud_alerts = db.execute('''
        SELECT a.*, u.name as user_name, e.name as event_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        WHERE a.fraud_score > 0.5
        ORDER BY a.timestamp DESC
        LIMIT 5
    ''').fetchall()
    
    return render_template('dashboard/admin_dashboard.html',
                         stats=dict(stats) if stats else {},
                         recent_attendance=recent_attendance,
                         fraud_alerts=fraud_alerts)

@admin_bp.route('/users')
@admin_required
def manage_users():
    """Manage users"""
    db = get_db()
    
    users = db.execute('''
        SELECT u.*, 
               (SELECT COUNT(*) FROM attendance WHERE user_id = u.id) as attendance_count,
               (SELECT status FROM id_verification WHERE user_id = u.id AND id_type = 'MOODLE') as verification_status
        FROM users u
        ORDER BY u.created_at DESC
    ''').fetchall()
    
    return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """Toggle user active status"""
    db = get_db()
    
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    new_status = not user.is_active
    db.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
    db.commit()
    
    log_audit('USER_STATUS_TOGGLED', 
             f'User {user_id} active status set to {new_status}', 
             session['admin_id'])
    
    return jsonify({'success': True, 'is_active': new_status})

@admin_bp.route('/verifications')
@admin_required
def verifications():
    """View ID verifications"""
    verifications = Verification.get_all_pending()
    return render_template('admin/verify_ids.html', verifications=verifications)

@admin_bp.route('/verification/<int:verification_id>/update', methods=['POST'])
@admin_required
def update_verification(verification_id):
    """Update verification status"""
    verification = Verification.get_by_id(verification_id)
    
    if not verification:
        return jsonify({'success': False, 'message': 'Verification not found'})
    
    status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    if status == 'VERIFIED':
        verification.approve(session['admin_id'], notes)
    elif status == 'REJECTED':
        verification.reject(session['admin_id'], notes)
    else:
        return jsonify({'success': False, 'message': 'Invalid status'})
    
    log_audit('VERIFICATION_UPDATED', 
             f'Verification {verification_id} updated to {status}', 
             session['admin_id'])
    
    return jsonify({'success': True, 'message': 'Verification updated successfully'})

@admin_bp.route('/events')
@admin_required
def manage_events():
    """Manage events"""
    active_events = Event.get_active_events()
    archived_events = Event.get_archived_events()
    
    return render_template('admin/manage_events.html',
                         active_events=active_events,
                         archived_events=archived_events)

@admin_bp.route('/event/create', methods=['GET', 'POST'])
@admin_required
def create_event():
    """Create new event"""
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        venue = request.form.get('venue', '')
        max_capacity = request.form.get('max_capacity', 100)
        
        try:
            event = Event.create(
                name=name,
                date=date,
                venue=venue,
                max_capacity=int(max_capacity),
                created_by=session['admin_id']
            )
            
            log_audit('EVENT_CREATED', f'Created event: {event.name}', session['admin_id'])
            flash('Event created successfully', 'success')
            return redirect(url_for('admin.manage_events'))
            
        except Exception as e:
            flash(f'Error creating event: {str(e)}', 'error')
    
    return render_template('events/create_event.html')

@admin_bp.route('/event/<int:event_id>/delete', methods=['POST'])
@admin_required
def delete_event(event_id):
    """Delete/archive event"""
    event = Event.get_by_id(event_id)
    
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'})
    
    delete_type = request.form.get('delete_type', 'soft')
    
    if delete_type == 'soft':
        event.soft_delete(deleted_by=session['admin_id'])
        message = 'Event archived successfully'
    else:
        # Hard delete - check for dependencies
        db = get_db()
        attendance_count = db.execute('SELECT COUNT(*) FROM attendance WHERE event_id = ?', 
                                     (event_id,)).fetchone()[0]
        
        if attendance_count > 0:
            return jsonify({'success': False, 
                          'message': 'Cannot delete event with attendance records'})
        
        db.execute('DELETE FROM events WHERE id = ?', (event_id,))
        db.commit()
        message = 'Event deleted permanently'
    
    log_audit('EVENT_DELETED', f'Event {event_id} {delete_type} deleted', session['admin_id'])
    return jsonify({'success': True, 'message': message})

@admin_bp.route('/event/<int:event_id>/restore', methods=['POST'])
@admin_required
def restore_event(event_id):
    """Restore archived event"""
    event = Event.get_by_id(event_id)
    
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'})
    
    event.restore()
    
    log_audit('EVENT_RESTORED', f'Restored event {event_id}', session['admin_id'])
    return jsonify({'success': True, 'message': 'Event restored successfully'})

@admin_bp.route('/lectures')
@admin_required
def manage_lectures():
    """Manage lectures"""
    lectures = Lecture.get_active_lectures()
    return render_template('admin/manage_lectures.html', lectures=lectures)

@admin_bp.route('/lecture/create', methods=['GET', 'POST'])
@admin_required
def create_lecture():
    """Create new lecture"""
    if request.method == 'POST':
        subject = request.form.get('subject')
        faculty = request.form.get('faculty')
        time = request.form.get('time')
        
        try:
            lecture = Lecture.create(
                subject=subject,
                faculty=faculty,
                time=time
            )
            
            log_audit('LECTURE_CREATED', f'Created lecture: {lecture.subject}', session['admin_id'])
            flash('Lecture created successfully', 'success')
            return redirect(url_for('admin.manage_lectures'))
            
        except Exception as e:
            flash(f'Error creating lecture: {str(e)}', 'error')
    
    return render_template('admin/create_lecture.html')

@admin_bp.route('/lecture/<int:lecture_id>/delete', methods=['POST'])
@admin_required
def delete_lecture(lecture_id):
    """Delete lecture"""
    lecture = Lecture.get_by_id(lecture_id)
    
    if not lecture:
        return jsonify({'success': False, 'message': 'Lecture not found'})
    
    lecture.delete()
    
    log_audit('LECTURE_DELETED', f'Deleted lecture {lecture_id}', session['admin_id'])
    return jsonify({'success': True, 'message': 'Lecture deleted successfully'})

@admin_bp.route('/security-logs')
@admin_required
def security_logs():
    """View security audit logs"""
    db = get_db()
    
    logs = db.execute('''
        SELECT al.*, u.name as user_name, u.moodle_id
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.timestamp DESC
        LIMIT 100
    ''').fetchall()
    
    return render_template('admin/security_logs.html', logs=logs)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Admin settings"""
    if request.method == 'POST':
        # Update settings
        auto_cleanup_days = request.form.get('auto_cleanup_days', 30)
        fraud_threshold = request.form.get('fraud_threshold', 0.7)
        
        # Save to database or config
        db = get_db()
        db.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', ('auto_cleanup_days', auto_cleanup_days, datetime.now()))
        
        db.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', ('fraud_threshold', fraud_threshold, datetime.now()))
        
        db.commit()
        
        log_audit('SETTINGS_UPDATED', 'Admin settings updated', session['admin_id'])
        flash('Settings updated successfully', 'success')
    
    # Get current settings
    db = get_db()
    settings = db.execute('SELECT key, value FROM settings').fetchall()
    settings_dict = {s['key']: s['value'] for s in settings}
    
    return render_template('admin/settings.html', settings=settings_dict)