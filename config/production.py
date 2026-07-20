"""
Production configuration
"""
import os
from pathlib import Path

class ProductionConfig:
    """Production environment configuration"""
    
    ENV = 'production'
    DEBUG = False
    TESTING = False
    
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 5000))
    
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 
                                   os.path.join(BASE_DIR, 'database', 'event_system.db'))
    
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    PERMANENT_SESSION_LIFETIME = 3600
    
    MAX_LOGIN_ATTEMPTS = 3
    LOCKOUT_TIME = 1800
    
    FRAUD_DETECTION_ENABLED = True
    ANOMALY_THRESHOLD = 0.6