"""
Feature extraction utilities for ML models
"""
import numpy as np
from datetime import datetime

class FeatureExtractor:
    """Extract features from attendance data for ML models"""
    
    @staticmethod
    def extract_temporal_features(timestamp):
        """Extract temporal features from timestamp"""
        dt = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
        
        return {
            'hour': dt.hour,
            'day_of_week': dt.weekday(),
            'day_of_month': dt.day,
            'month': dt.month,
            'is_weekend': 1 if dt.weekday() >= 5 else 0,
            'is_morning': 1 if 5 <= dt.hour < 12 else 0,
            'is_afternoon': 1 if 12 <= dt.hour < 17 else 0,
            'is_evening': 1 if 17 <= dt.hour < 21 else 0,
            'is_night': 1 if dt.hour >= 21 or dt.hour < 5 else 0
        }
    
    @staticmethod
    def extract_behavioral_features(user_history):
        """Extract behavioral features from user history"""
        if not user_history:
            return {
                'attendance_count': 0,
                'unique_events': 0,
                'avg_gap_hours': 0,
                'consistency_score': 0
            }
        
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in user_history]
        timestamps.sort()
        
        # Calculate gaps between attendances
        gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i-1]).total_seconds() / 3600  # hours
            gaps.append(gap)
        
        avg_gap = np.mean(gaps) if gaps else 0
        
        # Count unique events
        unique_events = len(set([r['event_id'] for r in user_history]))
        
        # Calculate consistency (inverse of variance in gaps)
        if len(gaps) > 1:
            gap_variance = np.var(gaps)
            consistency = 1.0 / (1.0 + gap_variance / 24)  # Normalize
        else:
            consistency = 0.5
        
        return {
            'attendance_count': len(user_history),
            'unique_events': unique_events,
            'avg_gap_hours': float(avg_gap),
            'consistency_score': float(consistency)
        }
    
    @staticmethod
    def extract_ip_features(ip_address, user_history):
        """Extract IP-related features"""
        if not user_history:
            return {
                'ip_novelty': 1.0,
                'ip_count': 0
            }
        
        known_ips = set([r.get('ip_address') for r in user_history if r.get('ip_address')])
        is_novel = ip_address not in known_ips if ip_address else True
        
        return {
            'ip_novelty': 1.0 if is_novel else 0.0,
            'ip_count': len(known_ips)
        }
    
    @staticmethod
    def create_feature_vector(record, user_history):
        """Create complete feature vector for ML model"""
        features = {}
        
        # Temporal features
        temporal = FeatureExtractor.extract_temporal_features(record['timestamp'])
        features.update(temporal)
        
        # Behavioral features
        behavioral = FeatureExtractor.extract_behavioral_features(user_history)
        features.update(behavioral)
        
        # IP features
        ip_features = FeatureExtractor.extract_ip_features(
            record.get('ip_address'), user_history
        )
        features.update(ip_features)
        
        # Event features
        features['event_popularity'] = FeatureExtractor.calculate_event_popularity(
            record['event_id']
        )
        
        return features
    
    @staticmethod
    def calculate_event_popularity(event_id):
        """Calculate how popular an event is"""
        from backend.utils.database import get_db
        
        db = get_db()
        result = db.execute('''
            SELECT COUNT(*) as count FROM registrations WHERE event_id = ?
        ''', (event_id,)).fetchone()
        
        return result['count'] if result else 0
    
    @staticmethod
    def normalize_features(feature_dict):
        """Normalize features to 0-1 range"""
        normalized = {}
        
        # Define normalization ranges
        ranges = {
            'hour': (0, 23),
            'day_of_week': (0, 6),
            'day_of_month': (1, 31),
            'month': (1, 12),
            'attendance_count': (0, 100),
            'unique_events': (0, 50),
            'avg_gap_hours': (0, 168),  # 1 week
            'consistency_score': (0, 1),
            'ip_novelty': (0, 1),
            'ip_count': (0, 20),
            'event_popularity': (0, 500)
        }
        
        for key, value in feature_dict.items():
            if key in ranges:
                min_val, max_val = ranges[key]
                if max_val > min_val:
                    normalized[key] = (value - min_val) / (max_val - min_val)
                else:
                    normalized[key] = 0.5
            else:
                # Binary features already 0/1
                normalized[key] = value
        
        return normalized