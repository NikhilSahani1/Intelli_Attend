"""
QR code generation and decoding utilities
"""
import qrcode
import os
import secrets
from datetime import datetime
from flask import current_app

def generate_qr_code(data, user_id, event_id):
    """Generate QR code image"""
    import qrcode
    from PIL import Image
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_str = secrets.token_hex(4)
    filename = f"qr_{user_id}_{event_id}_{timestamp}_{random_str}.png"
    
    # Save image
    qr_path = os.path.join(current_app.config['BASE_DIR'], 
                          'frontend', 'static', 'qr_codes', filename)
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    img.save(qr_path)
    
    return f"qr_codes/{filename}"

def decode_qr_data(qr_data):
    """Decode QR data to extract user and event info"""
    try:
        # Format: user_id-event_id-timestamp
        parts = qr_data.split('-')
        
        if len(parts) >= 3:
            user_id = int(parts[0])
            event_id = int(parts[1])
            timestamp = parts[2]
            return user_id, event_id, timestamp
        else:
            raise ValueError("Invalid QR data format")
            
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to decode QR data: {str(e)}")

def generate_manual_qr_data(event_id, lecture_id):
    """Generate data for manual QR code"""
    random_code = secrets.token_urlsafe(8)
    return f"MANUAL-{event_id}-{lecture_id}-{random_code}"

def validate_qr_timestamp(timestamp, max_age_minutes=30):
    """Validate if QR code is not expired"""
    try:
        qr_time = datetime.fromisoformat(timestamp)
        age = (datetime.now() - qr_time).total_seconds() / 60
        return age <= max_age_minutes
    except:
        return False