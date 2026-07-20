import sqlite3
import json
from datetime import datetime
import os

class SecurityLogger:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_dir = os.path.join(base_dir, 'database')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'security_logs.db')
        else:
            self.db_path = db_path
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        
        self._init_logs_table()
    
    def _init_logs_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                log_type TEXT,
                action TEXT,
                details TEXT,
                user_id INTEGER,
                user_name TEXT,
                user_email TEXT,
                ip_address TEXT,
                severity TEXT,
                duration_ms INTEGER
            )
        ''')
        conn.commit()
        conn.close()
    
    def log(self, log_type, action, details="", severity="INFO", user_info=None, duration_ms=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        user_id = None
        user_name = None
        user_email = None
        
        if user_info:
            user_id = user_info.get('id')
            user_name = user_info.get('name')
            user_email = user_info.get('email')
        
        cursor.execute('''
            INSERT INTO security_logs (log_type, action, details, user_id, user_name, user_email, severity, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log_type, action, details, user_id, user_name, user_email, severity, duration_ms))
        
        conn.commit()
        conn.close()
    
    def get_logs(self, limit=100):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM security_logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs

security_logger = SecurityLogger()

def log_activity(log_type, action, details="", severity="INFO", user_info=None):
    security_logger.log(log_type, action, details, severity, user_info)