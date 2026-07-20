"""
Lecture model for managing lectures
"""
from datetime import datetime
from backend.utils.database import get_db
from backend.utils.validators import sanitize_input

class Lecture:
    """Lecture model class"""
    
    def __init__(self, id=None, subject=None, faculty=None, time=None,
                 is_active=True, created_at=None):
        self.id = id
        self.subject = subject
        self.faculty = faculty
        self.time = time
        self.is_active = is_active
        self.created_at = created_at or datetime.now()
    
    @classmethod
    def create(cls, subject, faculty, time):
        """Create a new lecture"""
        # Sanitize inputs
        subject = sanitize_input(subject)
        faculty = sanitize_input(faculty)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO lectures (subject, faculty, time, is_active, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (subject, faculty, time, 1, datetime.now()))
            
            db.commit()
            lecture_id = cursor.lastrowid
            
            return cls.get_by_id(lecture_id)
            
        except Exception as e:
            db.rollback()
            raise e
    
    @classmethod
    def get_by_id(cls, lecture_id):
        """Get lecture by ID"""
        db = get_db()
        lecture_data = db.execute('''
            SELECT * FROM lectures WHERE id = ?
        ''', (lecture_id,)).fetchone()
        
        if lecture_data:
            return cls(**dict(lecture_data))
        return None
    
    @classmethod
    def get_active_lectures(cls):
        """Get all active lectures"""
        db = get_db()
        lectures_data = db.execute('''
            SELECT * FROM lectures WHERE is_active = 1 ORDER BY subject
        ''').fetchall()
        
        return [cls(**dict(lecture)) for lecture in lectures_data]
    
    def update(self, subject=None, faculty=None, time=None):
        """Update lecture details"""
        db = get_db()
        
        if subject:
            self.subject = sanitize_input(subject)
        if faculty:
            self.faculty = sanitize_input(faculty)
        if time:
            self.time = time
        
        db.execute('''
            UPDATE lectures 
            SET subject = ?, faculty = ?, time = ?
            WHERE id = ?
        ''', (self.subject, self.faculty, self.time, self.id))
        db.commit()
        
        return self
    
    def delete(self):
        """Soft delete lecture"""
        db = get_db()
        db.execute('''
            UPDATE lectures SET is_active = 0 WHERE id = ?
        ''', (self.id,))
        db.commit()
        
        self.is_active = False
        return self
    
    def get_events(self):
        """Get all events that include this lecture"""
        db = get_db()
        events_data = db.execute('''
            SELECT e.* 
            FROM events e
            JOIN event_lectures el ON e.id = el.event_id
            WHERE el.lecture_id = ? AND el.is_active = 1
        ''', (self.id,)).fetchall()
        
        from backend.models.event import Event
        return [Event(**dict(event)) for event in events_data]
    
    def to_dict(self):
        """Convert lecture to dictionary"""
        return {
            'id': self.id,
            'subject': self.subject,
            'faculty': self.faculty,
            'time': self.time,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }