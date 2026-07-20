"""
Database package initialization
Exports DatabaseManager and helper functions for Flask integration
"""
from database.db_manager import DatabaseManager, get_db, init_db, close_db

__all__ = ['DatabaseManager', 'get_db', 'init_db', 'close_db']