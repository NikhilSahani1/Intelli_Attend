"""
Security utilities for authentication, rate limiting, and headers
"""
from datetime import datetime, timedelta
from functools import wraps
from flask import session, flash, redirect, url_for, request
import threading

# Rate limiting storage
login_attempts = {}
attempts_lock = threading.Lock()

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME = 900  # 15 minutes

def is_locked_out(identifier):
    """Check if an identifier is locked out due to too many attempts"""
    with attempts_lock:
        entry = login_attempts.get(identifier)
        if not entry:
            return False
        
        locked_until = entry.get('locked_until')
        if locked_until and datetime.now().timestamp() < locked_until:
            return True
        
        # Clear expired lock
        if locked_until and datetime.now().timestamp() >= locked_until:
            del login_attempts[identifier]
        
        return False

def record_login_attempt(identifier, success):
    """Record a login attempt for rate limiting"""
    with attempts_lock:
        now_ts = datetime.now().timestamp()
        entry = login_attempts.get(identifier)
        
        if success:
            # Clear on successful login
            if identifier in login_attempts:
                del login_attempts[identifier]
            return
        
        if not entry:
            login_attempts[identifier] = {'attempts': 1, 'locked_until': None}
        else:
            entry['attempts'] = entry.get('attempts', 0) + 1
            if entry['attempts'] >= MAX_LOGIN_ATTEMPTS:
                entry['locked_until'] = now_ts + LOCKOUT_TIME
            login_attempts[identifier] = entry

def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('auth.user_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required', 'error')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def setup_security_headers(app):
    """Setup security headers for all responses"""
    
    @app.after_request
    def add_security_headers(response):
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Strict Transport Security (only in production)
        if app.config.get('ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Content Security Policy
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self' ws: wss:;"
        )
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy
        response.headers['Permissions-Policy'] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        
        return response