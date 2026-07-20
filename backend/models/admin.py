"""
Admin model for managing administrator accounts
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from backend.utils.database import get_db
from backend.utils.validators import sanitize_input

class Admin:
    """Admin model class"""
    
    def __init__(self, id=None, username=None, password=None, is_active=True,
                 last_login=None, created_at=None):
        self.id = id
        self.username = username
        self.password = password
        self.is_active = is_active
        self.last_login = last_login
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, username, password):
        """Create a new admin"""
        # Sanitize inputs
        username = sanitize_input(username)
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO admins (username, password, created_at)
                VALUES (?, ?, ?)
            ''', (username, hashed_password, datetime.now()))
            
            db.commit()
            admin_id = cursor.lastrowid
            
            return cls.get_by_id(admin_id)
            
        except Exception as e:
            db.rollback()
            raise e
    
    @classmethod
    def get_by_id(cls, admin_id):
        """Get admin by ID"""
        db = get_db()
        admin_data = db.execute('''
            SELECT * FROM admins WHERE id = ?
        ''', (admin_id,)).fetchone()
        
        if admin_data:
            return cls(**dict(admin_data))
        return None
    
    @classmethod
    def get_by_username(cls, username):
        """Get admin by username"""
        db = get_db()
        admin_data = db.execute('''
            SELECT * FROM admins WHERE username = ?
        ''', (username,)).fetchone()
        
        if admin_data:
            return cls(**dict(admin_data))
        return None
    
    def verify_password(self, password):
        """Verify admin password"""
        return check_password_hash(self.password, password)
    
    def update_last_login(self):
        """Update last login timestamp"""
        db = get_db()
        db.execute('''
            UPDATE admins SET last_login = ? WHERE id = ?
        ''', (datetime.now(), self.id))
        db.commit()
        self.last_login = datetime.now()
    
    def to_dict(self):
        """Convert admin to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }