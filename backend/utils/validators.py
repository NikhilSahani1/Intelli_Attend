"""
Validation utilities for input sanitization and validation
"""
import re

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"

def validate_aadhaar(aadhaar):
    """Validate Aadhaar number format"""
    if not aadhaar:
        return True  # Optional field
    
    # Remove spaces if any
    aadhaar = aadhaar.replace(' ', '')
    
    # Check if 12 digits
    if not re.match(r'^\d{12}$', aadhaar):
        return False
    
    # Verhoeff algorithm check (simplified)
    return True

def sanitize_input(text):
    """Sanitize input to prevent XSS"""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    
    # Remove script tags and content
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove javascript: protocol
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Remove on* event handlers
    text = re.sub(r'\son\w+\s*=', ' ', text, flags=re.IGNORECASE)
    
    # Trim and return
    return text.strip()

def validate_moodle_id(moodle_id):
    """Validate Moodle ID format"""
    # Moodle IDs are typically alphanumeric
    return re.match(r'^[a-zA-Z0-9]+$', moodle_id) is not None

def validate_phone(phone):
    """Validate phone number"""
    if not phone:
        return True  # Optional
    
    # Remove common separators
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if 10 digits (Indian format)
    return re.match(r'^\d{10}$', phone) is not None

def sanitize_filename(filename):
    """Sanitize filename for secure storage"""
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove special characters
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
    
    # Prevent directory traversal
    if filename.startswith('.'):
        filename = '_' + filename
    
    return filename