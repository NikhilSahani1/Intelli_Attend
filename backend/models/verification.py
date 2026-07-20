"""
Verification model for managing ID verifications
"""
from datetime import datetime
from backend.utils.database import get_db
from backend.utils.validators import sanitize_input

class Verification:
    """ID Verification model class"""
    
    def __init__(self, id=None, user_id=None, id_type=None, id_number=None,
                 verified_by=None, verified_at=None, status='PENDING',
                 notes=None, created_at=None):
        self.id = id
        self.user_id = user_id
        self.id_type = id_type
        self.id_number = id_number
        self.verified_by = verified_by
        self.verified_at = verified_at
        self.status = status
        self.notes = notes
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, user_id, id_type, id_number):
        """Create a new verification request"""
        # Sanitize inputs
        id_number = sanitize_input(id_number)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO id_verification (user_id, id_type, id_number, 
                                           status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, id_type, id_number, 'PENDING', datetime.now()))
            
            db.commit()
            verification_id = cursor.lastrowid
            
            return cls.get_by_id(verification_id)
            
        except Exception as e:
            db.rollback()
            raise e
    
    @classmethod
    def get_by_id(cls, verification_id):
        """Get verification by ID"""
        db = get_db()
        verification_data = db.execute('''
            SELECT * FROM id_verification WHERE id = ?
        ''', (verification_id,)).fetchone()
        
        if verification_data:
            return cls(**dict(verification_data))
        return None
    
    @classmethod
    def get_pending_for_user(cls, user_id):
        """Get pending verifications for a user"""
        db = get_db()
        verifications = db.execute('''
            SELECT * FROM id_verification 
            WHERE user_id = ? AND status = 'PENDING'
            ORDER BY created_at DESC
        ''', (user_id,)).fetchall()
        
        return [cls(**dict(v)) for v in verifications]
    
    @classmethod
    def get_all_pending(cls):
        """Get all pending verifications"""
        db = get_db()
        verifications = db.execute('''
            SELECT iv.*, u.name as user_name, u.email 
            FROM id_verification iv
            JOIN users u ON iv.user_id = u.id
            WHERE iv.status = 'PENDING'
            ORDER BY iv.created_at DESC
        ''').fetchall()
        
        return [dict(v) for v in verifications]
    
    def approve(self, admin_id, notes=None):
        """Approve verification"""
        db = get_db()
        
        self.status = 'VERIFIED'
        self.verified_by = admin_id
        self.verified_at = datetime.now()
        if notes:
            self.notes = sanitize_input(notes)
        
        db.execute('''
            UPDATE id_verification 
            SET status = ?, verified_by = ?, verified_at = ?, notes = ?
            WHERE id = ?
        ''', (self.status, self.verified_by, self.verified_at, self.notes, self.id))
        db.commit()
        
        # Check if all user's verifications are approved
        self.check_user_verification_status()
        
        return self
    
    def reject(self, admin_id, notes):
        """Reject verification"""
        db = get_db()
        
        self.status = 'REJECTED'
        self.verified_by = admin_id
        self.verified_at = datetime.now()
        self.notes = sanitize_input(notes)
        
        db.execute('''
            UPDATE id_verification 
            SET status = ?, verified_by = ?, verified_at = ?, notes = ?
            WHERE id = ?
        ''', (self.status, self.verified_by, self.verified_at, self.notes, self.id))
        db.commit()
        
        # Update user verification status
        db.execute('''
            UPDATE users SET verification_status = 'REJECTED' 
            WHERE id = ?
        ''', (self.user_id,))
        db.commit()
        
        return self
    
    def check_user_verification_status(self):
        """Check if user has all verifications approved"""
        db = get_db()
        
        # Check if any verifications are still pending or rejected
        result = db.execute('''
            SELECT COUNT(*) as count 
            FROM id_verification 
            WHERE user_id = ? AND status != 'VERIFIED'
        ''', (self.user_id,)).fetchone()
        
        if result and result['count'] == 0:
            # All verifications are approved
            db.execute('''
                UPDATE users SET verification_status = 'VERIFIED' 
                WHERE id = ?
            ''', (self.user_id,))
            db.commit()
    
    def to_dict(self):
        """Convert verification to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'id_type': self.id_type,
            'id_number': self.id_number,
            'verified_by': self.verified_by,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }