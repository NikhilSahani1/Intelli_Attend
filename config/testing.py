"""
Testing configuration
"""
import os
from pathlib import Path

class TestingConfig:
    """Testing environment configuration"""
    
    # Flask settings
    ENV = 'testing'
    DEBUG = True
    TESTING = True
    
    # Server settings
    HOST = '127.0.0.1'
    PORT = 5001
    
    # Database - use in-memory for testing
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = ':memory:'
    
    # Security
    SECRET_KEY = 'test-secret-key'
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate limiting (disabled for testing)
    MAX_LOGIN_ATTEMPTS = 999
    LOCKOUT_TIME = 1
    
    # ML Settings
    FACE_ENCODINGS_PATH = os.path.join(BASE_DIR, 'tests', 'test_data', 'face_encodings')
    TRAINED_MODELS_PATH = os.path.join(BASE_DIR, 'tests', 'test_data', 'trained_models')
    FRAUD_DETECTION_ENABLED = True
    ANOMALY_THRESHOLD = 0.5
    SPOOF_DETECTION_ENABLED = True
    
    # Auto cleanup
    EVENT_AUTO_CLEANUP_DAYS = 1
    EVENT_SOFT_DELETE = True
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'tests', 'test_uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    # Logging
    LOG_LEVEL = 'DEBUG'
    LOG_FILE = os.path.join(BASE_DIR, 'tests', 'test_logs', 'test.log')
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Preserve context for testing
    PRESERVE_CONTEXT_ON_EXCEPTION = False