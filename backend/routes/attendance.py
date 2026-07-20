"""
Attendance routes for marking and viewing attendance
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime

from backend.models.attendance import Attendance
from backend.models.event import Event
from backend.models.user import User
from backend.utils.database import get_db
from backend.utils.security import admin_required, login_required
from backend.utils.audit import log_audit
from backend.utils.qr_generator import generate_qr_code, decode_qr_data

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('/scanner')
@admin_required
def scanner():
    """QR Code scanner page"""
    db = get_db()
    
    # Get active events
    events = Event.get_active_events()
    
    # Get all lectures
    lectures = db.execute('''
        SELECT * FROM lectures WHERE is_active = 1 ORDER BY subject
    ''').fetchall()
    
    return render_template('attendance/scanner.html',
                         events=events,
                         lectures=lectures)

@attendance_bp.route('/mark', methods=['POST'])
@admin_required
def mark_attendance():
    """Mark attendance from QR code"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'})
    
    qr_data = data.get('qr_data')
    event_id = data.get('event_id')
    lecture_id = data.get('lecture_id')
    ip_address = request.remote_addr
    
    if not qr_data:
        return jsonify({'success': False, 'message': 'No QR data'})
    
    # Check if manual QR
    if qr_data.startswith('MANUAL-'):
        return process_manual_qr(qr_data, event_id, lecture_id, ip_address)
    
    # Decode regular QR
    try:
        user_id, qr_event_id, timestamp = decode_qr_data(qr_data)
        
        # Verify event matches
        if event_id and qr_event_id != int(event_id):
            return jsonify({'success': False, 'message': 'QR code does not match selected event'})
        
        # Get user
        user = User.get_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Check if user is verified
        if not user.is_verified():
            return jsonify({'success': False, 'message': 'User not verified'})
        
        # Check if user is registered for event
        db = get_db()
        registration = db.execute('''
            SELECT * FROM registrations 
            WHERE user_id = ? AND event_id = ?
        ''', (user_id, qr_event_id)).fetchone()
        
        if not registration:
            return jsonify({'success': False, 'message': 'User not registered for this event'})
        
        # Mark attendance
        result = Attendance.mark_attendance(
            user_id=user_id,
            event_id=qr_event_id,
            lecture_id=lecture_id or 1,
            ip_address=ip_address,
            verification_type='QR',
            verified_by=session['admin_id']
        )
        
        if result['success']:
            log_audit('ATTENDANCE_MARKED', 
                     f'Attendance marked for {user.name}', 
                     session['admin_id'])
            
            return jsonify({
                'success': True,
                'message': f'Attendance marked for {user.name}',
                'attendance': result['attendance'],
                'fraud_detection': result.get('fraud_detection', {})
            })
        else:
            return jsonify({'success': False, 'message': result['message']})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def process_manual_qr(qr_data, event_id, lecture_id, ip_address):
    """Process manual QR code"""
    try:
        # Format: MANUAL-event_id-lecture_id-code
        parts = qr_data.split('-')
        if len(parts) < 4:
            return jsonify({'success': False, 'message': 'Invalid manual QR format'})
        
        manual_event_id = int(parts[1])
        manual_lecture_id = int(parts[2])
        code = parts[3]
        
        # Verify matches selected
        if event_id and manual_event_id != int(event_id):
            return jsonify({'success': False, 'message': 'QR does not match selected event'})
        
        if lecture_id and manual_lecture_id != int(lecture_id):
            return jsonify({'success': False, 'message': 'QR does not match selected lecture'})
        
        # Get event and lecture details
        db = get_db()
        event = db.execute('SELECT * FROM events WHERE id = ?', (manual_event_id,)).fetchone()
        lecture = db.execute('SELECT * FROM lectures WHERE id = ?', (manual_lecture_id,)).fetchone()
        
        if not event or not lecture:
            return jsonify({'success': False, 'message': 'Event or lecture not found'})
        
        log_audit('MANUAL_QR_SCANNED', 
                 f'Manual QR scanned for {event["name"]}', 
                 session['admin_id'])
        
        return jsonify({
            'success': True,
            'message': f'Manual QR valid for {event["name"]} - {lecture["subject"]}',
            'event_name': event['name'],
            'lecture_name': lecture['subject']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@attendance_bp.route('/manual', methods=['GET', 'POST'])
@admin_required
def manual_attendance():
    """Manual attendance entry"""
    if request.method == 'POST':
        user_identifier = request.form.get('user_identifier')
        event_id = request.form.get('event_id')
        lecture_id = request.form.get('lecture_id')
        ip_address = request.remote_addr
        
        if not all([user_identifier, event_id, lecture_id]):
            flash('All fields are required', 'error')
            return redirect(url_for('attendance.manual_attendance'))
        
        # Find user
        db = get_db()
        user = None
        
        # Try different identifiers
        if '@' in user_identifier:
            user = User.get_by_email(user_identifier)
        elif user_identifier.isdigit():
            user = User.get_by_id(int(user_identifier))
            if not user:
                user = User.get_by_moodle_id(user_identifier)
        else:
            # Search by name
            user_data = db.execute('''
                SELECT * FROM users WHERE name LIKE ? LIMIT 1
            ''', (f'%{user_identifier}%',)).fetchone()
            if user_data:
                user = User(**dict(user_data))
        
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('attendance.manual_attendance'))
        
        # Check registration
        registration = db.execute('''
            SELECT * FROM registrations 
            WHERE user_id = ? AND event_id = ?
        ''', (user.id, event_id)).fetchone()
        
        if not registration:
            flash(f'{user.name} is not registered for this event', 'error')
            return redirect(url_for('attendance.manual_attendance'))
        
        # Mark attendance
        result = Attendance.mark_attendance(
            user_id=user.id,
            event_id=event_id,
            lecture_id=lecture_id,
            ip_address=ip_address,
            verification_type='MANUAL',
            verified_by=session['admin_id']
        )
        
        if result['success']:
            log_audit('MANUAL_ATTENDANCE', 
                     f'Manual attendance for {user.name}', 
                     session['admin_id'])
            flash(f'Attendance marked for {user.name}', 'success')
        else:
            flash(result['message'], 'error')
        
        return redirect(url_for('attendance.manual_attendance'))
    
    # GET request
    db = get_db()
    events = Event.get_active_events()
    lectures = db.execute('SELECT * FROM lectures WHERE is_active = 1').fetchall()
    
    return render_template('attendance/manual_attendance.html',
                         events=events,
                         lectures=lectures)

@attendance_bp.route('/log')
@admin_required
def attendance_log():
    """View attendance log"""
    db = get_db()
    
    # Get filters
    event_id = request.args.get('event_id')
    user_id = request.args.get('user_id')
    date = request.args.get('date')
    
    query = '''
        SELECT a.*, u.name as user_name, u.moodle_id, e.name as event_name,
               l.subject as lecture_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE 1=1
    '''
    params = []
    
    if event_id:
        query += ' AND a.event_id = ?'
        params.append(event_id)
    
    if user_id:
        query += ' AND a.user_id = ?'
        params.append(user_id)
    
    if date:
        query += ' AND DATE(a.timestamp) = ?'
        params.append(date)
    
    query += ' ORDER BY a.timestamp DESC LIMIT 100'
    
    logs = db.execute(query, params).fetchall()
    
    # Get events for filter
    events = Event.get_active_events()
    
    return render_template('attendance/attendance_log.html',
                         logs=logs,
                         events=events)

@attendance_bp.route('/generate-qr/<int:event_id>')
@admin_required
def generate_manual_qr(event_id):
    """Generate manual QR code for event"""
    event = Event.get_by_id(event_id)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin.manage_events'))
    
    db = get_db()
    lectures = db.execute('''
        SELECT l.* 
        FROM lectures l
        JOIN event_lectures el ON l.id = el.lecture_id
        WHERE el.event_id = ? AND el.is_active = 1
        ORDER BY el.sequence_order
    ''', (event_id,)).fetchall()
    
    return render_template('attendance/generate_manual_qr.html',
                         event=event,
                         lectures=lectures)

@attendance_bp.route('/generate-qr-code', methods=['POST'])
@admin_required
def generate_qr_code_endpoint():
    """Generate QR code API"""
    event_id = request.form.get('event_id')
    lecture_id = request.form.get('lecture_id')
    manual_code = request.form.get('manual_code', '')
    
    if not event_id or not lecture_id:
        return jsonify({'success': False, 'message': 'Event and lecture required'})
    
    # Generate QR data
    if not manual_code:
        import secrets
        manual_code = secrets.token_urlsafe(8)
    
    qr_data = f"MANUAL-{event_id}-{lecture_id}-{manual_code}"
    
    # Generate QR code image
    qr_filename = generate_qr_code(qr_data, f"manual_{event_id}_{lecture_id}", event_id)
    
    db = get_db()
    event = db.execute('SELECT name FROM events WHERE id = ?', (event_id,)).fetchone()
    lecture = db.execute('SELECT subject FROM lectures WHERE id = ?', (lecture_id,)).fetchone()
    
    return jsonify({
        'success': True,
        'qr_path': qr_filename,
        'manual_code': manual_code,
        'qr_data': qr_data,
        'event_name': event['name'] if event else 'Unknown',
        'lecture_name': lecture['subject'] if lecture else 'Unknown'
    })