"""
User model for managing user data and operations
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from backend.utils.database import get_db
from backend.utils.validators import validate_email, validate_password, sanitize_input

class User:
    """User model class"""
    
    def __init__(self, id=None, name=None, moodle_id=None, email=None, 
                 password=None, aadhaar_number=None, student_id=None,
                 phone_number=None, is_active=True, verification_status='PENDING',
                 created_at=None, last_login=None):
        self.id = id
        self.name = name
        self.moodle_id = moodle_id
        self.email = email
        self.password = password
        self.aadhaar_number = aadhaar_number
        self.student_id = student_id
        self.phone_number = phone_number
        self.is_active = is_active
        self.verification_status = verification_status
        self.created_at = created_at or datetime.now()
        self.last_login = last_login
    
    @classmethod
    def create(cls, name, moodle_id, email, password, aadhaar_number=None, 
               student_id=None, phone_number=None):
        """Create a new user"""
        # Validate inputs
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        is_valid, msg = validate_password(password)
        if not is_valid:
            raise ValueError(msg)
        
        # Sanitize inputs
        name = sanitize_input(name)
        moodle_id = sanitize_input(moodle_id)
        email = sanitize_input(email)
        aadhaar_number = sanitize_input(aadhaar_number) if aadhaar_number else None
        student_id = sanitize_input(student_id) if student_id else None
        phone_number = sanitize_input(phone_number) if phone_number else None
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (name, moodle_id, email, password, 
                                 aadhaar_number, student_id, phone_number,
                                 created_at, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, moodle_id, email, hashed_password,
                  aadhaar_number, student_id, phone_number,
                  datetime.now(), 'PENDING'))
            
            db.commit()
            user_id = cursor.lastrowid
            
            # Create verification entries
            cls.create_verification_entries(user_id, moodle_id, aadhaar_number, student_id)
            
            return cls.get_by_id(user_id)
            
        except Exception as e:
            db.rollback()
            raise e
    
    @classmethod
    def create_verification_entries(cls, user_id, moodle_id, aadhaar_number, student_id):
        """Create verification entries for user IDs"""
        db = get_db()
        cursor = db.cursor()
        
        # Check if id_verification table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='id_verification'")
        if cursor.fetchone():
            # Add Moodle ID verification
            cursor.execute('''
                INSERT INTO id_verification (user_id, id_type, id_number, status, created_at)
                VALUES (?, 'MOODLE', ?, 'PENDING', ?)
            ''', (user_id, moodle_id, datetime.now()))
            
            # Add Aadhaar verification if provided
            if aadhaar_number:
                cursor.execute('''
                    INSERT INTO id_verification (user_id, id_type, id_number, status, created_at)
                    VALUES (?, 'AADHAAR', ?, 'PENDING', ?)
                ''', (user_id, aadhaar_number, datetime.now()))
            
            # Add Student ID verification if provided
            if student_id:
                cursor.execute('''
                    INSERT INTO id_verification (user_id, id_type, id_number, status, created_at)
                    VALUES (?, 'STUDENT_ID', ?, 'PENDING', ?)
                ''', (user_id, student_id, datetime.now()))
            
            db.commit()
    
    @classmethod
    def get_by_id(cls, user_id):
        """Get user by ID"""
        db = get_db()
        user_data = db.execute('''
            SELECT * FROM users WHERE id = ?
        ''', (user_id,)).fetchone()
        
        if user_data:
            return cls(**dict(user_data))
        return None
    
    @classmethod
    def get_by_moodle_id(cls, moodle_id):
        """Get user by Moodle ID"""
        db = get_db()
        user_data = db.execute('''
            SELECT * FROM users WHERE moodle_id = ?
        ''', (moodle_id,)).fetchone()
        
        if user_data:
            return cls(**dict(user_data))
        return None
    
    @classmethod
    def get_by_email(cls, email):
        """Get user by email"""
        db = get_db()
        user_data = db.execute('''
            SELECT * FROM users WHERE email = ?
        ''', (email,)).fetchone()
        
        if user_data:
            return cls(**dict(user_data))
        return None
    
    def verify_password(self, password):
        """Verify user password"""
        return check_password_hash(self.password, password)
    
    def update_last_login(self):
        """Update last login timestamp"""
        db = get_db()
        db.execute('''
            UPDATE users SET last_login = ? WHERE id = ?
        ''', (datetime.now(), self.id))
        db.commit()
        self.last_login = datetime.now()
    
    def is_verified(self):
        """Check if user is verified"""
        if self.verification_status == 'VERIFIED':
            return True
        
        # Check id_verification table
        db = get_db()
        result = db.execute('''
            SELECT COUNT(*) as count FROM id_verification 
            WHERE user_id = ? AND status = 'VERIFIED'
        ''', (self.id,)).fetchone()
        
        return result['count'] > 0 if result else False
    
    def get_verification_status(self):
        """Get detailed verification status"""
        db = get_db()
        
        # Get all verification entries
        verifications = db.execute('''
            SELECT id_type, status, verified_at, notes
            FROM id_verification
            WHERE user_id = ?
            ORDER BY id_type
        ''', (self.id,)).fetchall()
        
        return [dict(v) for v in verifications]
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'moodle_id': self.moodle_id,
            'email': self.email,
            'aadhaar_number': self.aadhaar_number,
            'student_id': self.student_id,
            'phone_number': self.phone_number,
            'is_active': self.is_active,
            'verification_status': self.verification_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }