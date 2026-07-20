"""
Event model for managing events
"""
from datetime import datetime
from backend.utils.database import get_db
from backend.utils.validators import sanitize_input

class Event:
    """Event model class"""
    
    def __init__(self, id=None, name=None, date=None, venue='', max_capacity=100,
                 current_registrations=0, is_active=True, created_by=None,
                 created_at=None, deleted_at=None, deleted_by=None):
        self.id = id
        self.name = name
        self.date = date
        self.venue = venue
        self.max_capacity = max_capacity
        self.current_registrations = current_registrations
        self.is_active = is_active
        self.created_by = created_by
        self.created_at = created_at or datetime.now()
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by
    
    @classmethod
    def create(cls, name, date, venue='', max_capacity=100, created_by=None):
        """Create a new event"""
        # Sanitize inputs
        name = sanitize_input(name)
        venue = sanitize_input(venue)
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO events (name, date, venue, max_capacity, 
                                   current_registrations, is_active, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, date, venue, max_capacity, 0, 1, created_by, datetime.now()))
            
            db.commit()
            event_id = cursor.lastrowid
            
            return cls.get_by_id(event_id)
            
        except Exception as e:
            db.rollback()
            raise e
    
    @classmethod
    def get_by_id(cls, event_id):
        """Get event by ID"""
        db = get_db()
        event_data = db.execute('''
            SELECT * FROM events WHERE id = ?
        ''', (event_id,)).fetchone()
        
        if event_data:
            return cls(**dict(event_data))
        return None
    
    @classmethod
    def get_active_events(cls):
        """Get all active events"""
        db = get_db()
        events_data = db.execute('''
            SELECT * FROM events WHERE is_active = 1 ORDER BY date DESC
        ''').fetchall()
        
        return [cls(**dict(event)) for event in events_data]
    
    @classmethod
    def get_archived_events(cls):
        """Get all archived events"""
        db = get_db()
        events_data = db.execute('''
            SELECT * FROM events WHERE is_active = 0 ORDER BY date DESC
        ''').fetchall()
        
        return [cls(**dict(event)) for event in events_data]
    
    def update(self, name=None, date=None, venue=None, max_capacity=None):
        """Update event details"""
        db = get_db()
        
        if name:
            self.name = sanitize_input(name)
        if date:
            self.date = date
        if venue is not None:
            self.venue = sanitize_input(venue)
        if max_capacity:
            self.max_capacity = max_capacity
        
        db.execute('''
            UPDATE events 
            SET name = ?, date = ?, venue = ?, max_capacity = ?
            WHERE id = ?
        ''', (self.name, self.date, self.venue, self.max_capacity, self.id))
        db.commit()
        
        return self
    
    def soft_delete(self, deleted_by=None):
        """Soft delete event"""
        db = get_db()
        db.execute('''
            UPDATE events 
            SET is_active = 0, deleted_at = ?, deleted_by = ?
            WHERE id = ?
        ''', (datetime.now(), deleted_by, self.id))
        db.commit()
        
        self.is_active = False
        self.deleted_at = datetime.now()
        self.deleted_by = deleted_by
        
        return self
    
    def restore(self):
        """Restore soft-deleted event"""
        db = get_db()
        db.execute('''
            UPDATE events 
            SET is_active = 1, deleted_at = NULL, deleted_by = NULL
            WHERE id = ?
        ''', (self.id,))
        db.commit()
        
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
        
        return self
    
    def get_lectures(self):
        """Get all lectures for this event"""
        db = get_db()
        lectures_data = db.execute('''
            SELECT l.*, el.sequence_order 
            FROM lectures l
            JOIN event_lectures el ON l.id = el.lecture_id
            WHERE el.event_id = ? AND el.is_active = 1
            ORDER BY el.sequence_order
        ''', (self.id,)).fetchall()
        
        from backend.models.lecture import Lecture
        return [Lecture(**dict(lecture)) for lecture in lectures_data]
    
    def add_lecture(self, lecture_id):
        """Add a lecture to this event"""
        db = get_db()
        
        # Get next sequence order
        result = db.execute('''
            SELECT MAX(sequence_order) as max_order 
            FROM event_lectures 
            WHERE event_id = ?
        ''', (self.id,)).fetchone()
        
        next_order = (result['max_order'] or 0) + 1
        
        try:
            db.execute('''
                INSERT INTO event_lectures (event_id, lecture_id, sequence_order)
                VALUES (?, ?, ?)
            ''', (self.id, lecture_id, next_order))
            db.commit()
            return True
        except Exception:
            return False
    
    def remove_lecture(self, lecture_id):
        """Remove a lecture from this event"""
        db = get_db()
        db.execute('''
            UPDATE event_lectures 
            SET is_active = 0 
            WHERE event_id = ? AND lecture_id = ?
        ''', (self.id, lecture_id))
        db.commit()
        return True
    
    def get_registrations_count(self):
        """Get number of registrations for this event"""
        db = get_db()
        result = db.execute('''
            SELECT COUNT(*) as count FROM registrations WHERE event_id = ?
        ''', (self.id,)).fetchone()
        return result['count'] if result else 0
    
    def get_attendance_count(self):
        """Get total attendance count for this event"""
        db = get_db()
        result = db.execute('''
            SELECT COUNT(*) as count FROM attendance WHERE event_id = ?
        ''', (self.id,)).fetchone()
        return result['count'] if result else 0
    
    def is_full(self):
        """Check if event is at full capacity"""
        return self.current_registrations >= self.max_capacity
    
    def to_dict(self):
        """Convert event to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date,
            'venue': self.venue,
            'max_capacity': self.max_capacity,
            'current_registrations': self.current_registrations,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'deleted_by': self.deleted_by,
            'registrations_count': self.get_registrations_count(),
            'attendance_count': self.get_attendance_count()
        }