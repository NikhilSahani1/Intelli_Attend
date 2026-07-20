"""
Utilities package initialization
"""
from backend.utils.database import get_db, init_db, close_db
from backend.utils.security import (
    login_required, admin_required, is_locked_out, 
    record_login_attempt, setup_security_headers
)
from backend.utils.validators import (
    validate_email, validate_password, sanitize_input, validate_aadhaar
)
from backend.utils.qr_generator import generate_qr_code, decode_qr_data
from backend.utils.audit import log_audit

__all__ = [
    'get_db', 'init_db', 'close_db',
    'login_required', 'admin_required', 'is_locked_out',
    'record_login_attempt', 'setup_security_headers',
    'validate_email', 'validate_password', 'sanitize_input', 'validate_aadhaar',
    'generate_qr_code', 'decode_qr_data',
    'log_audit'
]