"""
Audit logging utilities
"""
from datetime import datetime
from backend.utils.database import get_db

def log_audit(action, description=None, user_id=None):
    """Log an audit event"""
    try:
        from flask import request
        
        db = get_db()
        ip_address = request.remote_addr if request else 'system'
        user_agent = request.headers.get('User-Agent', 'Unknown') if request else 'system'
        
        db.execute('''
            INSERT INTO audit_log (user_id, action, description, ip_address, user_agent, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action, description, ip_address, user_agent, datetime.now()))
        
        db.commit()
        
    except Exception as e:
        # Don't let audit logging failures break the app
        print(f"Audit logging failed: {e}")

def get_user_audit_logs(user_id, limit=50):
    """Get audit logs for a specific user"""
    db = get_db()
    
    logs = db.execute('''
        SELECT * FROM audit_log 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    
    return logs

def get_recent_audit_logs(limit=100):
    """Get recent audit logs"""
    db = get_db()
    
    logs = db.execute('''
        SELECT al.*, u.name as user_name, u.moodle_id
        FROM audit_log al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.timestamp DESC 
        LIMIT ?
    ''', (limit,)).fetchall()
    
    return logs

def get_audit_stats(days=7):
    """Get audit statistics"""
    db = get_db()
    
    stats = db.execute('''
        SELECT 
            DATE(timestamp) as date,
            COUNT(*) as total,
            COUNT(DISTINCT user_id) as unique_users,
            action,
            COUNT(*) as action_count
        FROM audit_log
        WHERE timestamp >= DATE('now', ?)
        GROUP BY DATE(timestamp), action
        ORDER BY date DESC, action_count DESC
    ''', (f'-{days} days',)).fetchall()
    
    return stats