"""
Models package initialization
"""
from backend.models.user import User
from backend.models.admin import Admin
from backend.models.event import Event
from backend.models.lecture import Lecture
from backend.models.attendance import Attendance
from backend.models.verification import Verification

__all__ = ['User', 'Admin', 'Event', 'Lecture', 'Attendance', 'Verification']