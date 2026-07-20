"""
Anomaly Detection for identifying unusual patterns
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_models import MLModelBase

class AnomalyDetector(MLModelBase):
    """Detect anomalies in attendance patterns"""
    
    def __init__(self):
        super().__init__('anomaly_detector')
        
    def detect_time_anomalies(self, attendance_data):
        """
        Detect time-based anomalies
        
        Parameters:
        - attendance_data: List of dicts with timestamp
        
        Returns:
        - List of anomalies with severity
        """
        if len(attendance_data) < 10:
            return []
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(attendance_data)
        
        # Extract hour from timestamp
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        hourly_counts = df.groupby('hour').size().reset_index(name='count')
        
        # Calculate statistics
        mean_count = hourly_counts['count'].mean()
        std_count = hourly_counts['count'].std()
        
        anomalies = []
        
        for _, row in hourly_counts.iterrows():
            hour = int(row['hour'])
            count = row['count']
            
            # Z-score for anomaly detection
            z_score = (count - mean_count) / (std_count if std_count > 0 else 1)
            
            if abs(z_score) > 2:
                severity = 'HIGH' if abs(z_score) > 3 else 'MEDIUM'
                anomalies.append({
                    'type': 'time_anomaly',
                    'hour': f"{hour:02d}:00",
                    'count': int(count),
                    'expected': float(mean_count),
                    'z_score': float(z_score),
                    'severity': severity,
                    'color': 'danger' if severity == 'HIGH' else 'warning'
                })
        
        return anomalies
    
    def detect_user_anomalies(self, attendance_data):
        """
        Detect anomalous user behavior
        
        Parameters:
        - attendance_data: List of dicts with user attendance
        
        Returns:
        - List of users with anomalous behavior
        """
        if len(attendance_data) < 5:
            return []
        
        df = pd.DataFrame(attendance_data)
        
        if 'user_id' not in df.columns:
            return []
        
        # Group by user
        user_stats = []
        
        for user_id in df['user_id'].unique():
            user_data = df[df['user_id'] == user_id]
            
            # Get user name if available
            user_name = 'Unknown'
            if 'user_name' in user_data.columns and len(user_data) > 0:
                user_name = user_data.iloc[0]['user_name']
            
            stats = {
                'user_id': user_id,
                'user_name': user_name,
                'attendance_count': len(user_data),
                'avg_fraud_score': user_data['fraud_score'].mean() if 'fraud_score' in user_data.columns else 0,
                'max_fraud_score': user_data['fraud_score'].max() if 'fraud_score' in user_data.columns else 0,
                'events_attended': user_data['event_id'].nunique() if 'event_id' in user_data.columns else 0
            }
            user_stats.append(stats)
        
        if not user_stats:
            return []
        
        df_stats = pd.DataFrame(user_stats)
        
        # Calculate thresholds
        mean_attendance = df_stats['attendance_count'].mean()
        std_attendance = df_stats['attendance_count'].std()
        mean_fraud = df_stats['avg_fraud_score'].mean()
        std_fraud = df_stats['avg_fraud_score'].std()
        
        anomalies = []
        
        for _, user in df_stats.iterrows():
            reasons = []
            
            # Check for unusually high attendance
            if user['attendance_count'] > mean_attendance + 2 * std_attendance:
                reasons.append(f"Unusually high attendance ({user['attendance_count']})")
            
            # Check for high fraud score
            if user['avg_fraud_score'] > mean_fraud + 1.5 * std_fraud:
                reasons.append(f"High fraud score ({user['avg_fraud_score']:.2f})")
            
            # Check for no attendance
            if user['attendance_count'] == 0:
                reasons.append("No attendance records")
            
            if reasons:
                anomalies.append({
                    'user_id': int(user['user_id']),
                    'user_name': user['user_name'],
                    'reasons': ', '.join(reasons),
                    'fraud_score': f"{user['avg_fraud_score']:.2f}",
                    'attendance': int(user['attendance_count'])
                })
        
        return anomalies
    
    def detect_event_anomalies(self, attendance_data):
        """
        Detect anomalous events
        
        Parameters:
        - attendance_data: List of dicts with event attendance
        
        Returns:
        - List of events with anomalies
        """
        if len(attendance_data) < 3:
            return []
        
        df = pd.DataFrame(attendance_data)
        
        if 'event_id' not in df.columns:
            return []
        
        # Group by event
        event_stats = []
        
        for event_id in df['event_id'].unique():
            event_data = df[df['event_id'] == event_id]
            
            # Get event name if available
            event_name = f"Event {event_id}"
            if 'event_name' in event_data.columns and len(event_data) > 0:
                event_name = event_data.iloc[0]['event_name']
            
            # Get event date if available
            event_date = 'Unknown'
            if 'event_date' in event_data.columns and len(event_data) > 0:
                event_date = event_data.iloc[0]['event_date']
            
            stats = {
                'event_id': event_id,
                'event_name': event_name,
                'date': event_date,
                'attendance': len(event_data),
                'avg_fraud_score': event_data['fraud_score'].mean() if 'fraud_score' in event_data.columns else 0
            }
            event_stats.append(stats)
        
        if not event_stats:
            return []
        
        df_stats = pd.DataFrame(event_stats)
        
        # Calculate thresholds
        mean_attendance = df_stats['attendance'].mean()
        std_attendance = df_stats['attendance'].std()
        mean_fraud = df_stats['avg_fraud_score'].mean()
        std_fraud = df_stats['avg_fraud_score'].std()
        
        anomalies = []
        
        for _, event in df_stats.iterrows():
            reasons = []
            
            # Low attendance
            if event['attendance'] < 5:
                reasons.append(f"Low attendance ({event['attendance']})")
            
            # High fraud score
            if event['avg_fraud_score'] > mean_fraud + 1.5 * std_fraud:
                reasons.append(f"High fraud score ({event['avg_fraud_score']:.2f})")
            
            if reasons:
                anomalies.append({
                    'event_id': int(event['event_id']),
                    'event_name': event['event_name'],
                    'date': event['date'],
                    'attendance': int(event['attendance']),
                    'fraud_score': f"{event['avg_fraud_score']:.2f}",
                    'reason': ', '.join(reasons)
                })
        
        return anomalies
    
    def detect_all(self, attendance_data):
        """
        Run all anomaly detection methods
        
        Returns:
        - Dictionary with all anomalies
        """
        time_anomalies = self.detect_time_anomalies(attendance_data)
        user_anomalies = self.detect_user_anomalies(attendance_data)
        event_anomalies = self.detect_event_anomalies(attendance_data)
        
        return {
            'time_anomalies': time_anomalies,
            'user_anomalies': user_anomalies,
            'event_anomalies': event_anomalies,
            'stats': {
                'total_anomalies': len(time_anomalies) + len(user_anomalies) + len(event_anomalies),
                'time_count': len(time_anomalies),
                'user_count': len(user_anomalies),
                'event_count': len(event_anomalies)
            }
        }