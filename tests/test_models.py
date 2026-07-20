"""
Unit tests for database models
"""
import pytest
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models.user import User
from backend.models.admin import Admin
from backend.models.event import Event
from backend.models.lecture import Lecture
from backend.models.attendance import Attendance
from backend.models.verification import Verification
from database.db_manager import DatabaseManager

class TestModels:
    """Test suite for database models"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test database"""
        self.db = DatabaseManager(':memory:')
        yield
        self.db.close_all()
    
    def test_create_user(self):
        """Test user creation"""
        user = User.create(
            name="Test User",
            moodle_id="TEST001",
            email="test@example.com",
            password="Test@123",
            phone_number="1234567890"
        )
        
        assert user.id is not None
        assert user.name == "Test User"
        assert user.moodle_id == "TEST001"
        assert user.email == "test@example.com"
        assert user.verification_status == "PENDING"
    
    def test_user_verification(self):
        """Test user verification"""
        user = User.create(
            name="Test User",
            moodle_id="TEST002",
            email="test2@example.com",
            password="Test@123"
        )
        
        assert not user.is_verified()
        
        # Create verification
        Verification.create(user.id, "MOODLE", "TEST002")
        Verification.create(user.id, "AADHAAR", "123456789012")
        
        # Admin verification
        admin = Admin.create("testadmin", "Admin@123")
        
        verifications = Verification.get_pending_for_user(user.id)
        for v in verifications:
            v.approve(admin.id)
        
        updated_user = User.get_by_id(user.id)
        assert updated_user.is_verified()
    
    def test_create_event(self):
        """Test event creation"""
        event = Event.create(
            name="Test Event",
            date="2024-12-25",
            venue="Test Venue",
            max_capacity=50
        )
        
        assert event.id is not None
        assert event.name == "Test Event"
        assert event.max_capacity == 50
        assert event.is_active
    
    def test_event_lectures(self):
        """Test event lecture association"""
        event = Event.create("Test Event", "2024-12-25")
        lecture = Lecture.create("Test Subject", "Test Faculty", "10:00")
        
        event.add_lecture(lecture.id)
        lectures = event.get_lectures()
        
        assert len(lectures) == 1
        assert lectures[0].subject == "Test Subject"
    
    def test_create_lecture(self):
        """Test lecture creation"""
        lecture = Lecture.create(
            subject="Mathematics",
            faculty="Dr. Smith",
            time="09:00"
        )
        
        assert lecture.id is not None
        assert lecture.subject == "Mathematics"
        assert lecture.faculty == "Dr. Smith"
        assert lecture.is_active
    
    def test_mark_attendance(self):
        """Test attendance marking"""
        user = User.create("Test User", "TEST003", "test3@example.com", "Test@123")
        event = Event.create("Test Event", "2024-12-25")
        lecture = Lecture.create("Test Subject", "Test Faculty", "10:00")
        
        event.add_lecture(lecture.id)
        
        result = Attendance.mark_attendance(
            user_id=user.id,
            event_id=event.id,
            lecture_id=lecture.id,
            ip_address="127.0.0.1",
            verification_type="QR"
        )
        
        assert result['success']
        assert result['attendance']['user_id'] == user.id
        assert 'fraud_detection' in result
    
    def test_duplicate_attendance_prevention(self):
        """Test prevention of duplicate attendance"""
        user = User.create("Test User", "TEST004", "test4@example.com", "Test@123")
        event = Event.create("Test Event", "2024-12-25")
        lecture = Lecture.create("Test Subject", "Test Faculty", "10:00")
        
        event.add_lecture(lecture.id)
        
        # First attendance
        result1 = Attendance.mark_attendance(
            user_id=user.id,
            event_id=event.id,
            lecture_id=lecture.id,
            ip_address="127.0.0.1"
        )
        
        assert result1['success']
        
        # Second attendance (should fail)
        result2 = Attendance.mark_attendance(
            user_id=user.id,
            event_id=event.id,
            lecture_id=lecture.id,
            ip_address="127.0.0.1"
        )
        
        assert not result2['success']
        assert 'already marked' in result2['message'].lower()
    
    def test_event_capacity(self):
        """Test event capacity limits"""
        event = Event.create("Test Event", "2024-12-25", max_capacity=2)
        
        user1 = User.create("User 1", "U001", "u1@test.com", "Test@123")
        user2 = User.create("User 2", "U002", "u2@test.com", "Test@123")
        user3 = User.create("User 3", "U003", "u3@test.com", "Test@123")
        
        # Register first two users
        from backend.utils.database import get_db
        db = get_db()
        
        db.execute("INSERT INTO registrations (user_id, event_id) VALUES (?, ?)", 
                  (user1.id, event.id))
        db.execute("INSERT INTO registrations (user_id, event_id) VALUES (?, ?)", 
                  (user2.id, event.id))
        db.commit()
        
        event.current_registrations = 2
        
        assert event.is_full()
        
        # Try to register third user
        with pytest.raises(Exception):
            db.execute("INSERT INTO registrations (user_id, event_id) VALUES (?, ?)", 
                      (user3.id, event.id))
    
    def test_audit_logging(self):
        """Test audit logging"""
        from backend.utils.audit import log_audit
        
        user = User.create("Test User", "TEST005", "test5@example.com", "Test@123")
        
        log_audit("TEST_ACTION", "Test description", user.id)
        
        from backend.utils.audit import get_recent_audit_logs
        logs = get_recent_audit_logs(limit=10)
        
        assert len(logs) > 0
        assert logs[0]['action'] == "TEST_ACTION"

### tests/test_routes.py
```python
"""
Unit tests for Flask routes
"""
import pytest
import sys
import os
import json
from flask import Flask

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from config.testing import TestingConfig
from database.db_manager import DatabaseManager

class TestRoutes:
    """Test suite for Flask routes"""
    
    @pytest.fixture(autouse=True)
def setup(self):
        """Setup test client"""
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Setup test database
        self.db = DatabaseManager(':memory:')
        
        yield
        
        self.app_context.pop()
    
    def test_home_page(self):
        """Test home page"""
        response = self.client.get('/')
        assert response.status_code == 200
        assert b'Intelligent Attendance' in response.data
    
    def test_user_registration(self):
        """Test user registration"""
        response = self.client.post('/auth/register', data={
            'name': 'Test User',
            'moodle_id': 'TEST001',
            'email': 'test@example.com',
            'password': 'Test@123',
            'confirm_password': 'Test@123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Registration successful' in response.data
    
    def test_user_login(self):
        """Test user login"""
        # First register
        self.client.post('/auth/register', data={
            'name': 'Test User',
            'moodle_id': 'TEST002',
            'email': 'test2@example.com',
            'password': 'Test@123',
            'confirm_password': 'Test@123'
        })
        
        # Try login (should fail because not verified)
        response = self.client.post('/auth/user/login', data={
            'moodle_id': 'TEST002',
            'password': 'Test@123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'pending verification' in response.data.lower()
    
    def test_admin_login(self):
        """Test admin login"""
        response = self.client.post('/auth/admin/login', data={
            'username': 'admin',
            'password': 'Admin@123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Admin login successful' in response.data
    
    def test_create_event_admin(self):
        """Test event creation by admin"""
        # Login as admin
        self.client.post('/auth/admin/login', data={
            'username': 'admin',
            'password': 'Admin@123'
        })
        
        # Create event
        response = self.client.post('/admin/event/create', data={
            'name': 'Test Event',
            'date': '2024-12-25',
            'venue': 'Test Venue',
            'max_capacity': '100'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Event created successfully' in response.data
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        # Test events API
        response = self.client.get('/api/events')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'events' in data

### tests/test_ml_models.py
```python
"""
Unit tests for ML models
"""
import pytest
import sys
import os
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ml_models.fraud_detection.anomaly_detector import AnomalyDetector
from backend.ml_models.fraud_detection.duplicate_detector import DuplicateDetector
from backend.ml_models.face_recognition.anti_spoofing import AntiSpoofing
from backend.ml_models.face_recognition.face_encoder import FaceEncoder

class TestMLModels:
    """Test suite for ML models"""
    
    def setup_method(self):
        """Setup test data"""
        self.anomaly_detector = AnomalyDetector()
        self.duplicate_detector = DuplicateDetector()
        self.anti_spoofing = AntiSpoofing()
        self.face_encoder = FaceEncoder()
    
    def test_anomaly_detection(self):
        """Test anomaly detection"""
        # Create sample attendance records
        base_time = datetime.now()
        records = []
        
        # Normal pattern
        for i in range(10):
            records.append({
                'user_id': 1,
                'event_id': 1,
                'timestamp': (base_time + timedelta(days=i)).isoformat(),
                'ip_address': '192.168.1.1'
            })
        
        # Anomalous record
        anomalous = {
            'user_id': 1,
            'event_id': 1,
            'timestamp': (base_time + timedelta(hours=1)).isoformat(),
            'ip_address': '10.0.0.1'
        }
        
        # Train detector
        self.anomaly_detector.train_model(records)
        
        # Test detection
        result = self.anomaly_detector.detect_anomalies(anomalous, records)
        
        assert 'is_anomaly' in result
        assert 'score' in result
    
    def test_duplicate_detection(self):
        """Test duplicate attendance detection"""
        base_time = datetime.now()
        
        # Create records with duplicates
        records = [
            {
                'user_id': 1,
                'event_id': 1,
                'timestamp': base_time.isoformat(),
                'ip_address': '192.168.1.1'
            },
            {
                'user_id': 1,
                'event_id': 1,
                'timestamp': (base_time + timedelta(minutes=2)).isoformat(),
                'ip_address': '192.168.1.1'
            },
            {
                'user_id': 2,
                'event_id': 1,
                'timestamp': (base_time + timedelta(minutes=5)).isoformat(),
                'ip_address': '192.168.1.2'
            }
        ]
        
        duplicates = self.duplicate_detector.detect_duplicate_attendance(
            records, time_window=300
        )
        
        assert len(duplicates) > 0
        assert duplicates[0]['user_id'] == 1
    
    def test_anti_spoofing(self):
        """Test anti-spoofing detection"""
        import cv2
        import numpy as np
        
        # Create a test frame (simulated)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        result = self.anti_spoofing.detect_spoof(frame)
        
        assert 'is_spoof' in result
        assert 'confidence' in result
    
    def test_face_encoding(self):
        """Test face encoding (requires actual face image)"""
        # This test would need a real face image
        # For now, just test the initialization
        assert self.face_encoder is not None
    
    def test_feature_extraction(self):
        """Test feature extraction for ML"""
        from backend.ml_models.utils.feature_extractor import FeatureExtractor
        
        features = FeatureExtractor.extract_temporal_features(
            datetime.now().isoformat()
        )
        
        assert 'hour' in features
        assert 'day_of_week' in features
        assert 'is_weekend' in features
    
    def test_model_loading(self):
        """Test model loading utilities"""
        from backend.ml_models.utils.model_loader import ModelLoader
        
        loader = ModelLoader(models_path='tests/test_data/')
        
        # Test saving and loading
        test_data = {'test': 'data'}
        loader.save_model(test_data, 'test_model')
        
        loaded = loader.load_model('test_model')
        assert loaded == test_data
        
        # Cleanup
        loader.delete_model('test_model')

## Project Root Files

### requirements.txt
```txt
# Web Framework
Flask==2.3.3
Werkzeug==2.3.7
flask-socketio==5.3.4
eventlet==0.33.3
python-dotenv==1.0.0

# Database
sqlite3

# Machine Learning
tensorflow==2.13.0
scikit-learn==1.3.0
numpy==1.24.3
pandas==2.0.3
scipy==1.11.1

# Computer Vision & Face Recognition
opencv-python==4.8.1.78
face-recognition==1.3.0
dlib==19.24.2
mediapipe==0.10.7
Pillow==10.0.0

# QR Code
qrcode==7.4.2
opencv-contrib-python==4.8.1.78

# Security
bcrypt==4.0.1
cryptography==41.0.3
itsdangerous==2.1.2
email-validator==2.0.0

# Utilities
python-dateutil==2.8.2
requests==2.31.0
gunicorn==21.2.0
click==8.1.6
blinker==1.6.2

# Testing
pytest==7.4.0
pytest-cov==4.1.0
pytest-flask==1.2.0
coverage==7.2.7

# Documentation
sphinx==7.1.2
sphinx-rtd-theme==1.2.2

# Monitoring & Logging
prometheus-flask-exporter==0.22.4
python-json-logger==2.0.7

# Celery for async tasks (optional)
celery==5.3.1
redis==4.6.0

# Email
flask-mail==0.9.1

# File uploads
flask-uploads==0.2.1

# Rate limiting
flask-limiter==3.3.1

# API documentation
flasgger==0.9.7.1

# CORS
flask-cors==4.0.0