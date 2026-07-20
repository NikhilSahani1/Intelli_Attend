"""
Attendance model with ML integration for fraud detection
"""
from datetime import datetime
from backend.utils.database import get_db
from backend.ml_models.fraud_detection.anomaly_detector import AnomalyDetector
from backend.ml_models.fraud_detection.duplicate_detector import DuplicateDetector

class Attendance:
    """Attendance model with ML-based fraud detection"""
    
    def __init__(self, id=None, user_id=None, event_id=None, lecture_id=None,
                 timestamp=None, ip_address=None, verification_type='QR',
                 verified_by=None, fraud_score=0.0, fraud_flags=None):
        self.id = id
        self.user_id = user_id
        self.event_id = event_id
        self.lecture_id = lecture_id
        self.timestamp = timestamp or datetime.now()
        self.ip_address = ip_address
        self.verification_type = verification_type
        self.verified_by = verified_by
        self.fraud_score = fraud_score
        self.fraud_flags = fraud_flags or []
        
        # Initialize ML detectors
        self.anomaly_detector = AnomalyDetector()
        self.duplicate_detector = DuplicateDetector()
    
    @classmethod
    def mark_attendance(cls, user_id, event_id, lecture_id, ip_address, 
                        verification_type='QR', verified_by=None, 
                        face_encoding=None):
        """Mark attendance with ML fraud detection"""
        
        db = get_db()
        
        # Check if already marked
        existing = db.execute('''
            SELECT * FROM attendance 
            WHERE user_id = ? AND event_id = ? AND lecture_id = ?
        ''', (user_id, event_id, lecture_id)).fetchone()
        
        if existing:
            return {
                'success': False,
                'message': 'Attendance already marked for this lecture',
                'existing': dict(existing)
            }
        
        # Create attendance record
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO attendance (user_id, event_id, lecture_id, timestamp,
                                   ip_address, verification_type, verified_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, event_id, lecture_id, datetime.now(),
              ip_address, verification_type, verified_by))
        
        db.commit()
        attendance_id = cursor.lastrowid
        
        # Get the created record
        attendance_data = db.execute('''
            SELECT a.*, u.name as user_name, e.name as event_name, l.subject as lecture_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            JOIN events e ON a.event_id = e.id
            JOIN lectures l ON a.lecture_id = l.id
            WHERE a.id = ?
        ''', (attendance_id,)).fetchone()
        
        attendance = cls(**dict(attendance_data))
        
        # Run ML fraud detection
        fraud_result = attendance.detect_fraud(face_encoding)
        
        # Update fraud score if needed
        if fraud_result['has_fraud']:
            attendance.update_fraud_score(attendance_id, fraud_result)
        
        return {
            'success': True,
            'attendance': attendance.to_dict(),
            'fraud_detection': fraud_result
        }
    
    def detect_fraud(self, face_encoding=None):
        """Run ML fraud detection algorithms"""
        fraud_flags = []
        fraud_score = 0.0
        
        # Get user's attendance history
        db = get_db()
        history = db.execute('''
            SELECT * FROM attendance 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''', (self.user_id,)).fetchall()
        
        history_dicts = [dict(h) for h in history]
        
        # 1. Anomaly detection
        if history_dicts:
            current_record = self.to_dict()
            anomaly_result = self.anomaly_detector.detect_anomalies(
                current_record, history_dicts
            )
            
            if anomaly_result['is_anomaly']:
                fraud_flags.append({
                    'type': 'anomaly',
                    'reason': anomaly_result['reason'],
                    'score': anomaly_result['score']
                })
                fraud_score += anomaly_result['score']
        
        # 2. Duplicate detection within time window
        duplicate_result = self.duplicate_detector.detect_duplicate_attendance(
            history_dicts + [self.to_dict()], 
            time_window=300  # 5 minutes
        )
        
        if duplicate_result:
            fraud_flags.extend(duplicate_result)
            fraud_score += sum([d.get('score', 0.5) for d in duplicate_result])
        
        # 3. Location/IP anomaly
        if history_dicts:
            ip_check = self.check_ip_anomaly(history_dicts)
            if ip_check:
                fraud_flags.append(ip_check)
                fraud_score += ip_check['score']
        
        # 4. Face recognition check (if provided)
        if face_encoding:
            face_check = self.check_face_match(face_encoding)
            if face_check and not face_check['match']:
                fraud_flags.append({
                    'type': 'face_mismatch',
                    'reason': 'Face does not match registered user',
                    'score': 0.9
                })
                fraud_score += 0.9
        
        # Normalize score to 0-1
        fraud_score = min(fraud_score, 1.0)
        
        return {
            'has_fraud': len(fraud_flags) > 0,
            'fraud_score': fraud_score,
            'fraud_flags': fraud_flags,
            'risk_level': self.get_risk_level(fraud_score)
        }
    
    def check_ip_anomaly(self, history):
        """Check if IP address is anomalous"""
        if not history:
            return None
        
        # Get unique IPs from history
        known_ips = set([h['ip_address'] for h in history if h['ip_address']])
        
        if self.ip_address not in known_ips and known_ips:
            return {
                'type': 'new_ip',
                'reason': f'New IP address: {self.ip_address}',
                'score': 0.3
            }
        
        return None
    
    def check_face_match(self, face_encoding):
        """Check if face matches registered user"""
        # This will be implemented by face recognition module
        from backend.ml_models.face_recognition.recognizer import FaceDetector
        
        detector = FaceDetector()
        return detector.verify_face(self.user_id, face_encoding)
    
    def get_risk_level(self, score):
        """Get risk level based on fraud score"""
        if score < 0.3:
            return 'LOW'
        elif score < 0.6:
            return 'MEDIUM'
        elif score < 0.8:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def update_fraud_score(self, attendance_id, fraud_result):
        """Update attendance record with fraud detection results"""
        db = get_db()
        db.execute('''
            UPDATE attendance 
            SET fraud_score = ?, fraud_flags = ?
            WHERE id = ?
        ''', (fraud_result['fraud_score'], 
              str(fraud_result['fraud_flags']), 
              attendance_id))
        db.commit()
    
    def to_dict(self):
        """Convert attendance to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_id': self.event_id,
            'lecture_id': self.lecture_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'verification_type': self.verification_type,
            'verified_by': self.verified_by,
            'fraud_score': self.fraud_score,
            'fraud_flags': self.fraud_flags
        }