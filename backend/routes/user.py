"""
User routes for dashboard and self-service
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime

from backend.models.user import User
from backend.models.event import Event
from backend.models.attendance import Attendance
from backend.utils.database import get_db
from backend.utils.security import user_required
from backend.utils.audit import log_audit
from backend.utils.qr_generator import generate_qr_code

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@user_required
def dashboard():
    """User dashboard"""
    user_id = session['user_id']
    db = get_db()
    
    # Get user details
    user = User.get_by_id(user_id)
    
    # Get upcoming events
    upcoming_events = db.execute('''
        SELECT e.*, 
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id) as registrations,
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id AND user_id = ?) as registered
        FROM events e
        WHERE e.date >= DATE('now') AND e.is_active = 1
        ORDER BY e.date
        LIMIT 5
    ''', (user_id,)).fetchall()
    
    # Get recent attendance
    recent_attendance = db.execute('''
        SELECT a.*, e.name as event_name, l.subject as lecture_name
        FROM attendance a
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE a.user_id = ?
        ORDER BY a.timestamp DESC
        LIMIT 10
    ''', (user_id,)).fetchall()
    
    # Get verification status
    verification_status = user.get_verification_status()
    
    return render_template('dashboard/user_dashboard.html',
                         user=user,
                         upcoming_events=upcoming_events,
                         recent_attendance=recent_attendance,
                         verification_status=verification_status)

@user_bp.route('/profile')
@user_required
def profile():
    """User profile"""
    user = User.get_by_id(session['user_id'])
    verification_status = user.get_verification_status()
    
    return render_template('user/profile.html', 
                         user=user, 
                         verification_status=verification_status)

@user_bp.route('/profile/update', methods=['POST'])
@user_required
def update_profile():
    """Update user profile"""
    user_id = session['user_id']
    db = get_db()
    
    phone_number = request.form.get('phone_number')
    
    db.execute('''
        UPDATE users SET phone_number = ? WHERE id = ?
    ''', (phone_number, user_id))
    db.commit()
    
    log_audit('PROFILE_UPDATED', 'User updated profile', user_id)
    flash('Profile updated successfully', 'success')
    
    return redirect(url_for('user.profile'))

@user_bp.route('/events')
@user_required
def events():
    """View available events"""
    user_id = session['user_id']
    db = get_db()
    
    events = db.execute('''
        SELECT e.*, 
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id) as registrations,
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id AND user_id = ?) as registered
        FROM events e
        WHERE e.is_active = 1
        ORDER BY e.date DESC
    ''', (user_id,)).fetchall()
    
    return render_template('events/events.html', events=events)

@user_bp.route('/event/<int:event_id>/register')
@user_required
def register_for_event(event_id):
    """Register for an event"""
    user_id = session['user_id']
    db = get_db()
    
    # Check if already registered
    existing = db.execute('''
        SELECT * FROM registrations 
        WHERE user_id = ? AND event_id = ?
    ''', (user_id, event_id)).fetchone()
    
    if existing:
        flash('You are already registered for this event', 'info')
        return redirect(url_for('user.events'))
    
    # Get event details
    event = Event.get_by_id(event_id)
    if not event or not event.is_active:
        flash('Event not found or unavailable', 'error')
        return redirect(url_for('user.events'))
    
    # Check capacity
    if event.is_full():
        flash('Event is at full capacity', 'error')
        return redirect(url_for('user.events'))
    
    # Register user
    db.execute('''
        INSERT INTO registrations (user_id, event_id, registered_at)
        VALUES (?, ?, ?)
    ''', (user_id, event_id, datetime.now()))
    
    # Update registration count
    db.execute('''
        UPDATE events 
        SET current_registrations = current_registrations + 1 
        WHERE id = ?
    ''', (event_id,))
    
    db.commit()
    
    # Generate QR code
    qr_data = f"{user_id}-{event_id}-{datetime.now().timestamp()}"
    qr_filename = generate_qr_code(qr_data, user_id, event_id)
    
    log_audit('EVENT_REGISTRATION', f'Registered for event {event_id}', user_id)
    flash('Successfully registered for event!', 'success')
    
    return render_template('user/registration_success.html',
                         event=event,
                         qr_filename=qr_filename)

@user_bp.route('/my-attendance')
@user_required
def my_attendance():
    """View user's attendance history"""
    user_id = session['user_id']
    db = get_db()
    
    attendance = db.execute('''
        SELECT a.*, e.name as event_name, l.subject as lecture_name,
               CASE 
                   WHEN a.fraud_score > 0.7 THEN 'HIGH RISK'
                   WHEN a.fraud_score > 0.4 THEN 'MEDIUM RISK'
                   ELSE 'LOW RISK'
               END as risk_level
        FROM attendance a
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE a.user_id = ?
        ORDER BY a.timestamp DESC
    ''', (user_id,)).fetchall()
    
    # Get statistics
    stats = db.execute('''
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT event_id) as unique_events,
            AVG(fraud_score) as avg_fraud_score
        FROM attendance
        WHERE user_id = ?
    ''', (user_id,)).fetchone()
    
    return render_template('user/my_attendance.html',
                         attendance=attendance,
                         stats=dict(stats) if stats else {})

@user_bp.route('/fraud-alerts')
@user_required
def my_fraud_alerts():
    """View fraud alerts for user"""
    user_id = session['user_id']
    db = get_db()
    
    alerts = db.execute('''
        SELECT a.*, e.name as event_name, l.subject as lecture_name
        FROM attendance a
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE a.user_id = ? AND a.fraud_score > 0.3
        ORDER BY a.timestamp DESC
    ''', (user_id,)).fetchall()
    
    return render_template('user/fraud_alerts.html', alerts=alerts)

@user_bp.route('/face-enrollment')
@user_required
def face_enrollment():
    """Face enrollment page"""
    user_id = session['user_id']
    
    # Check if already enrolled
    db = get_db()
    existing = db.execute('''
        SELECT * FROM face_encodings 
        WHERE user_id = ? AND is_active = 1
    ''', (user_id,)).fetchone()
    
    return render_template('user/face_enrollment.html', 
                         has_face=existing is not None)

@user_bp.route('/face-enrollment/upload', methods=['POST'])
@user_required
def upload_face():
    """Upload face for enrollment"""
    if 'face_image' not in request.files:
        return jsonify({'success': False, 'message': 'No image provided'})
    
    file = request.files['face_image']
    user_id = session['user_id']
    
    # This will be handled by the ML routes
    # Redirect to ML endpoint
    return redirect(url_for('ml.face_enroll'))