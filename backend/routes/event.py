"""
Event routes for managing events and lectures
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime

from backend.models.event import Event
from backend.models.lecture import Lecture
from backend.utils.database import get_db
from backend.utils.security import admin_required, login_required
from backend.utils.audit import log_audit

event_bp = Blueprint('event', __name__)

@event_bp.route('/list')
@login_required
def list_events():
    """List all events"""
    db = get_db()
    
    events = db.execute('''
        SELECT e.*, 
               (SELECT COUNT(*) FROM registrations WHERE event_id = e.id) as registrations,
               (SELECT COUNT(*) FROM attendance WHERE event_id = e.id) as attendance
        FROM events e
        WHERE e.is_active = 1
        ORDER BY e.date DESC
    ''').fetchall()
    
    return render_template('events/events.html', events=events)

@event_bp.route('/<int:event_id>')
@login_required
def view_event(event_id):
    """View event details"""
    event = Event.get_by_id(event_id)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('event.list_events'))
    
    lectures = event.get_lectures()
    
    db = get_db()
    registrations = db.execute('''
        SELECT COUNT(*) as count FROM registrations WHERE event_id = ?
    ''', (event_id,)).fetchone()
    
    return render_template('events/view_event.html',
                         event=event,
                         lectures=lectures,
                         registrations=registrations['count'])

@event_bp.route('/<int:event_id>/lectures')
@login_required
def event_lectures(event_id):
    """Get lectures for an event (API)"""
    event = Event.get_by_id(event_id)
    
    if not event:
        return jsonify({'success': False, 'message': 'Event not found'})
    
    lectures = event.get_lectures()
    
    return jsonify({
        'success': True,
        'lectures': [l.to_dict() for l in lectures]
    })

@event_bp.route('/<int:event_id>/attendance-report')
@admin_required
def attendance_report(event_id):
    """Generate attendance report for event"""
    event = Event.get_by_id(event_id)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin.manage_events'))
    
    db = get_db()
    
    # Get attendance summary
    summary = db.execute('''
        SELECT 
            u.id,
            u.name,
            u.moodle_id,
            COUNT(a.id) as attended_lectures,
            AVG(a.fraud_score) as avg_fraud_score
        FROM users u
        JOIN registrations r ON u.id = r.user_id
        LEFT JOIN attendance a ON u.id = a.user_id AND a.event_id = ?
        WHERE r.event_id = ?
        GROUP BY u.id
        ORDER BY u.name
    ''', (event_id, event_id)).fetchall()
    
    # Get lecture-wise attendance
    lectures = event.get_lectures()
    lecture_attendance = []
    
    for lecture in lectures:
        attendance = db.execute('''
            SELECT COUNT(*) as count 
            FROM attendance 
            WHERE event_id = ? AND lecture_id = ?
        ''', (event_id, lecture.id)).fetchone()
        
        lecture_attendance.append({
            'lecture': lecture,
            'count': attendance['count'] if attendance else 0
        })
    
    return render_template('events/attendance_report.html',
                         event=event,
                         summary=summary,
                         lecture_attendance=lecture_attendance)

@event_bp.route('/<int:event_id>/export-csv')
@admin_required
def export_attendance_csv(event_id):
    """Export attendance as CSV"""
    import csv
    import io
    from flask import Response
    
    event = Event.get_by_id(event_id)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('admin.manage_events'))
    
    db = get_db()
    
    data = db.execute('''
        SELECT 
            u.name,
            u.moodle_id,
            u.email,
            l.subject as lecture,
            a.timestamp,
            a.verification_type,
            a.fraud_score,
            a.ip_address
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE a.event_id = ?
        ORDER BY a.timestamp
    ''', (event_id,)).fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Name', 'Moodle ID', 'Email', 'Lecture', 'Timestamp', 
                     'Verification Type', 'Fraud Score', 'IP Address'])
    
    # Write data
    for row in data:
        writer.writerow([
            row['name'],
            row['moodle_id'],
            row['email'],
            row['lecture'],
            row['timestamp'],
            row['verification_type'],
            row['fraud_score'],
            row['ip_address']
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=attendance_{event_id}.csv'}
    )