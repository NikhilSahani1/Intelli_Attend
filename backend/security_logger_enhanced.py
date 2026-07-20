"""
Enhanced Security Logger - Captures all user and admin activities
"""
import sqlite3
import os
from datetime import datetime
from flask import request, session
import threading
import time

class EnhancedSecurityLogger:
    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create security_logs table if it doesn't exist"""
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
                user_role TEXT,
                ip_address TEXT,
                user_agent TEXT,
                severity TEXT,
                duration_ms INTEGER,
                additional_data TEXT
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON security_logs(timestamp DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_type ON security_logs(log_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user ON security_logs(user_id)')
        
        conn.commit()
        conn.close()
    
    def log(self, log_type, action, details, severity='INFO', user_info=None, duration_ms=None, additional_data=None):
        """Log an activity with enhanced details"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user info from session if not provided
            if not user_info:
                user_info = {}
                if 'user_id' in session:
                    user_info['id'] = session.get('user_id')
                    user_info['name'] = session.get('user_name', 'Unknown')
                    user_info['email'] = session.get('user_email', 'Unknown')
                    user_info['role'] = session.get('user_type', 'user')
                elif 'admin_id' in session:
                    user_info['id'] = session.get('admin_id')
                    user_info['name'] = session.get('admin_name', 'Admin')
                    user_info['email'] = 'admin@system.com'
                    user_info['role'] = 'admin'
            
            # Get IP address
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr) if request else 'Unknown'
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
            
            # Get User Agent
            user_agent = request.headers.get('User-Agent', 'Unknown')[:500] if request else 'Unknown'
            
            cursor.execute('''
                INSERT INTO security_logs (
                    log_type, action, details, user_id, user_name, user_email, user_role,
                    ip_address, user_agent, severity, duration_ms, additional_data, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_type.upper(), action, details,
                user_info.get('id'), user_info.get('name'), user_info.get('email'), user_info.get('role'),
                ip_address, user_agent, severity.upper(), duration_ms,
                json.dumps(additional_data) if additional_data else None,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Logging error: {e}")
            return False
    
    def get_logs(self, limit=100, offset=0, log_type=None, severity=None, user_id=None, search=None, days=None):
        """Retrieve logs with filters"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM security_logs WHERE 1=1"
            params = []
            
            if log_type and log_type != 'all':
                query += " AND log_type = ?"
                params.append(log_type.upper())
            
            if severity and severity != 'all':
                query += " AND severity = ?"
                params.append(severity.upper())
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if days:
                query += " AND timestamp >= datetime('now', ?)"
                params.append(f'-{days} days')
            
            if search:
                query += " AND (action LIKE ? OR details LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR ip_address LIKE ?)"
                search_pattern = f'%{search}%'
                params.extend([search_pattern] * 5)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            logs = cursor.execute(query, params).fetchall()
            conn.close()
            
            return [dict(log) for log in logs]
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []
    
    def get_stats(self):
        """Get log statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            total = cursor.execute("SELECT COUNT(*) FROM security_logs").fetchone()[0]
            today = cursor.execute("SELECT COUNT(*) FROM security_logs WHERE date(timestamp) = date('now')").fetchone()[0]
            warnings = cursor.execute("SELECT COUNT(*) FROM security_logs WHERE severity IN ('WARNING', 'ERROR')").fetchone()[0]
            auth_attempts = cursor.execute("SELECT COUNT(*) FROM security_logs WHERE log_type = 'AUTH'").fetchone()[0]
            
            conn.close()
            return {
                'total': total,
                'today': today,
                'warnings': warnings,
                'auth_attempts': auth_attempts
            }
        except:
            return {'total': 0, 'today': 0, 'warnings': 0, 'auth_attempts': 0}

import json

# Create global instance
security_logger_enhanced = None

def init_security_logger(db_path):
    global security_logger_enhanced
    security_logger_enhanced = EnhancedSecurityLogger(db_path)
    return security_logger_enhanced

def log_activity(log_type, action, details, severity='INFO', user_info=None, duration_ms=None):
    """Global function to log activities"""
    if security_logger_enhanced:
        return security_logger_enhanced.log(log_type, action, details, severity, user_info, duration_ms)
    return False