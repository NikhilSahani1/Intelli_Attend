"""
ML and Biometric routes for fraud detection
"""
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

from backend.ml_models.face_recognition.face_encoder import FaceEncoder
from backend.ml_models.face_recognition.anti_spoofing import AntiSpoofing
from backend.ml_models.fraud_detection.anomaly_detector import AnomalyDetector
from backend.ml_models.fraud_detection.duplicate_detector import DuplicateDetector
from backend.models.user import User
from backend.models.attendance import Attendance
from backend.utils.database import get_db
from backend.utils.audit import log_audit
from backend.utils.security import admin_required

ml_bp = Blueprint('ml', __name__)

# Initialize ML models
face_encoder = FaceEncoder()
anti_spoofing = AntiSpoofing()
anomaly_detector = AnomalyDetector()
duplicate_detector = DuplicateDetector()

# Load existing face encodings
face_encoder.load_encodings()

@ml_bp.route('/dashboard')
def ml_dashboard():
    """ML Dashboard with fraud statistics"""
    if 'admin_id' not in session:
        flash("Admin access required", "error")
        return redirect(url_for('auth.admin_login'))
    
    db = get_db()
    
    # Get fraud statistics
    fraud_stats = db.execute('''
        SELECT 
            COUNT(CASE WHEN fraud_score > 0.6 THEN 1 END) as high_risk,
            COUNT(CASE WHEN fraud_score BETWEEN 0.3 AND 0.6 THEN 1 END) as medium_risk,
            COUNT(CASE WHEN fraud_score < 0.3 THEN 1 END) as low_risk,
            AVG(fraud_score) as avg_fraud_score,
            COUNT(*) as total_attendance
        FROM attendance
        WHERE DATE(timestamp) = DATE('now')
    ''').fetchone()
    
    # Get recent fraud alerts
    fraud_alerts = db.execute('''
        SELECT a.*, u.name as user_name, u.moodle_id, e.name as event_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        WHERE a.fraud_score > 0.3
        ORDER BY a.timestamp DESC
        LIMIT 20
    ''').fetchall()
    
    return render_template('ml/ml_dashboard.html',
                         fraud_stats=dict(fraud_stats) if fraud_stats else {},
                         fraud_alerts=fraud_alerts)

@ml_bp.route('/face/enroll', methods=['GET', 'POST'])
def face_enroll():
    """Enroll face for a user"""
    if 'user_id' not in session and 'admin_id' not in session:
        flash("Login required", "error")
        return redirect(url_for('auth.user_login'))
    
    if request.method == 'POST':
        if 'face_image' not in request.files:
            return jsonify({'success': False, 'message': 'No image provided'})
        
        file = request.files['face_image']
        user_id = session.get('user_id') or request.form.get('user_id')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        # Get user details
        user = User.get_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Save image temporarily
        filename = secure_filename(f"face_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        temp_path = os.path.join('frontend/static/temp', filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        
        # Encode face
        result = face_encoder.encode_face(temp_path, user_id, user.name)
        
        # Clean up temp file
        os.remove(temp_path)
        
        if result['success']:
            log_audit("FACE_ENROLLED", f"Face enrolled for user {user_id}", 
                     session.get('admin_id') or session.get('user_id'))
            
            return jsonify({
                'success': True,
                'message': 'Face enrolled successfully',
                'quality': result.get('encoding_quality', {})
            })
        else:
            return jsonify({'success': False, 'message': result['message']})
    
    # GET request
    if 'admin_id' in session:
        # Admin can enroll for any user
        db = get_db()
        users = db.execute('''
            SELECT id, name, moodle_id FROM users 
            WHERE is_active = 1 
            ORDER BY name
        ''').fetchall()
        return render_template('ml/face_enroll.html', users=users, is_admin=True)
    else:
        # User enrolling themselves
        return render_template('ml/face_enroll.html', is_admin=False)

@ml_bp.route('/face/verify', methods=['POST'])
def face_verify():
    """Verify face during attendance"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    if 'face_image' not in request.files:
        return jsonify({'success': False, 'message': 'No image provided'})
    
    file = request.files['face_image']
    user_id = request.form.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'User ID required'})
    
    # Save image temporarily
    filename = secure_filename(f"verify_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    temp_path = os.path.join('frontend/static/temp', filename)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    file.save(temp_path)
    
    # First check for spoofing
    import cv2
    frame = cv2.imread(temp_path)
    spoof_result = anti_spoofing.detect_spoof(frame)
    
    if spoof_result['is_spoof']:
        os.remove(temp_path)
        return jsonify({
            'success': False,
            'message': 'Spoofing attempt detected!',
            'spoof_details': spoof_result
        })
    
    # Verify face
    result = face_encoder.verify_face(user_id, temp_path)
    os.remove(temp_path)
    
    return jsonify(result)

@ml_bp.route('/fraud/alerts')
def fraud_alerts():
    """View fraud alerts"""
    if 'admin_id' not in session:
        flash("Admin access required", "error")
        return redirect(url_for('auth.admin_login'))
    
    db = get_db()
    
    # Get all fraud alerts
    alerts = db.execute('''
        SELECT 
            a.id,
            a.timestamp,
            a.fraud_score,
            a.fraud_flags,
            a.verification_type,
            a.ip_address,
            u.name as user_name,
            u.moodle_id,
            e.name as event_name,
            l.subject as lecture_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        JOIN events e ON a.event_id = e.id
        JOIN lectures l ON a.lecture_id = l.id
        WHERE a.fraud_score > 0.3
        ORDER BY a.timestamp DESC
    ''').fetchall()
    
    # Parse fraud_flags JSON
    for alert in alerts:
        try:
            alert_dict = dict(alert)
            alert_dict['fraud_flags'] = json.loads(alert_dict['fraud_flags']) if alert_dict['fraud_flags'] else []
        except:
            alert_dict['fraud_flags'] = []
    
    return render_template('ml/fraud_alerts.html', alerts=alerts)

@ml_bp.route('/anomaly/report')
def anomaly_report():
    """Generate anomaly report"""
    if 'admin_id' not in session:
        flash("Admin access required", "error")
        return redirect(url_for('auth.admin_login'))
    
    db = get_db()
    
    # Get date range from query params
    days = request.args.get('days', 7, type=int)
    
    # Get anomaly statistics by day
    anomalies_by_day = db.execute('''
        SELECT 
            DATE(timestamp) as date,
            COUNT(CASE WHEN fraud_score > 0.6 THEN 1 END) as high_risk,
            COUNT(CASE WHEN fraud_score BETWEEN 0.3 AND 0.6 THEN 1 END) as medium_risk,
            COUNT(CASE WHEN fraud_score < 0.3 THEN 1 END) as low_risk,
            COUNT(*) as total
        FROM attendance
        WHERE timestamp >= DATE('now', ?)
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
    ''', (f'-{days} days',)).fetchall()
    
    # Get top fraudulent users
    top_users = db.execute('''
        SELECT 
            u.id,
            u.name,
            u.moodle_id,
            COUNT(a.id) as total_attendance,
            AVG(a.fraud_score) as avg_fraud_score,
            MAX(a.fraud_score) as max_fraud_score
        FROM users u
        JOIN attendance a ON u.id = a.user_id
        WHERE a.fraud_score > 0.3
        GROUP BY u.id
        HAVING total_attendance > 1
        ORDER BY avg_fraud_score DESC
        LIMIT 10
    ''').fetchall()
    
    return render_template('ml/anomaly_reports.html',
                         anomalies_by_day=anomalies_by_day,
                         top_users=top_users,
                         days=days)

@ml_bp.route('/train/models', methods=['POST'])
def train_models():
    """Train ML models with latest data"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    db = get_db()
    
    # Get all attendance data for training
    attendance_data = db.execute('''
        SELECT a.*, u.name as user_name
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp
    ''').fetchall()
    
    attendance_dicts = [dict(a) for a in attendance_data]
    
    # Train anomaly detector
    if len(attendance_dicts) > 100:
        anomaly_detector.train_model(attendance_dicts)
        
        log_audit("ML_MODELS_TRAINED", f"Trained models with {len(attendance_dicts)} records", 
                 session['admin_id'])
        
        return jsonify({
            'success': True,
            'message': f'Models trained successfully with {len(attendance_dicts)} records'
        })
    else:
        return jsonify({
            'success': False,
            'message': f'Need at least 100 records for training (got {len(attendance_dicts)})'
        })

@ml_bp.route('/stats')
def ml_stats():
    """Get ML statistics for dashboard"""
    if 'admin_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    db = get_db()
    
    # Get today's statistics
    today_stats = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN fraud_score > 0.6 THEN 1 ELSE 0 END) as high_risk,
            SUM(CASE WHEN fraud_score BETWEEN 0.3 AND 0.6 THEN 1 ELSE 0 END) as medium_risk,
            AVG(fraud_score) as avg_score
        FROM attendance
        WHERE DATE(timestamp) = DATE('now')
    ''').fetchone()
    
    # Get weekly trend
    weekly_trend = db.execute('''
        SELECT 
            DATE(timestamp) as date,
            AVG(fraud_score) as avg_score,
            COUNT(*) as count
        FROM attendance
        WHERE timestamp >= DATE('now', '-7 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    ''').fetchall()
    
    return jsonify({
        'success': True,
        'today': dict(today_stats) if today_stats else {},
        'weekly_trend': [dict(w) for w in weekly_trend]
    })