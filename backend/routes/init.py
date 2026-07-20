"""
Routes package initialization
"""
from backend.routes.auth import auth_bp
from backend.routes.admin import admin_bp
from backend.routes.user import user_bp
from backend.routes.event import event_bp
from backend.routes.attendance import attendance_bp
from backend.routes.ml_routes import ml_bp

__all__ = ['auth_bp', 'admin_bp', 'user_bp', 'event_bp', 'attendance_bp', 'ml_bp']