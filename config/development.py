"""
Development configuration
"""
import os
from pathlib import Path

class DevelopmentConfig:
    """Development environment configuration"""
    
    # Flask settings
    ENV = 'development'
    DEBUG = True
    TESTING = False
    
    # Server settings
    HOST = '127.0.0.1'
    PORT = 5000
    
    # Database
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'event_system.db')
    
    # Security
    SECRET_KEY = 'dev-secret-key-change-in-production'
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 7200  # 2 hours in seconds
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_TIME = 900  # 15 minutes in seconds
    
    # ML Settings
    FACE_ENCODINGS_PATH = os.path.join(BASE_DIR, 'frontend', 'static', 'face_encodings')
    TRAINED_MODELS_PATH = os.path.join(BASE_DIR, 'frontend', 'static', 'trained_models')
    FRAUD_DETECTION_ENABLED = True
    ANOMALY_THRESHOLD = 0.7
    
    # Auto cleanup
    EVENT_AUTO_CLEANUP_DAYS = 30
    EVENT_SOFT_DELETE = True