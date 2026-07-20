"""
Behavior analysis for fraud detection
"""
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

class BehaviorAnalyzer:
    """Analyze user behavior patterns for fraud detection"""
    
    def __init__(self):
        self.user_history = defaultdict(list)
        self.pattern_threshold = 0.8
    
    def analyze_attendance_pattern(self, user_id, attendance_records):
        """Analyze user's attendance pattern"""
        if len(attendance_records) < 5:
            return {'unusual_pattern': False, 'reason': 'Insufficient data'}
        
        # Extract features
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in attendance_records]
        
        # Check for regular patterns
        pattern_score = self.detect_regular_pattern(timestamps)
        
        # Check for unusual timing
        timing_score = self.detect_unusual_timing(timestamps)
        
        # Check for location patterns
        location_score = self.detect_location_pattern(attendance_records)
        
        unusual = (pattern_score + timing_score + location_score) / 3 > self.pattern_threshold
        
        return {
            'unusual_pattern': unusual,
            'pattern_score': float(pattern_score),
            'timing_score': float(timing_score),
            'location_score': float(location_score)
        }
    
    def detect_regular_pattern(self, timestamps):
        """Detect if attendance follows a regular pattern"""
        if len(timestamps) < 3:
            return 0.0
        
        # Calculate time differences
        diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() / 3600 
                 for i in range(len(timestamps)-1)]
        
        # Check variance
        variance = np.var(diffs) if len(diffs) > 1 else 0
        normalized_variance = min(variance / 24, 1.0)  # Normalize to 0-1
        
        # High variance suggests irregular pattern (potential fraud)
        return 1.0 - normalized_variance
    
    def detect_unusual_timing(self, timestamps):
        """Detect if attendance occurs at unusual times"""
        if len(timestamps) < 3:
            return 0.0
        
        # Get hours
        hours = [t.hour for t in timestamps]
        
        # Check if attendance always at same time (too regular)
        hour_counts = defaultdict(int)
        for h in hours:
            hour_counts[h] += 1
        
        most_common_hour = max(hour_counts.values()) if hour_counts else 0
        regularity_score = most_common_hour / len(hours)
        
        # Perfect regularity (always same time) could indicate automated attendance
        if regularity_score > 0.8:
            return regularity_score
        
        return 0.0
    
    def detect_location_pattern(self, records):
        """Detect unusual location patterns"""
        if len(records) < 3:
            return 0.0
        
        # Get unique IPs
        ips = [r.get('ip_address', '') for r in records if r.get('ip_address')]
        unique_ips = len(set(ips))
        
        # Too many IP changes might indicate proxy attendance
        if len(ips) > 0:
            ip_change_rate = unique_ips / len(ips)
            return min(ip_change_rate, 1.0)
        
        return 0.0
    
    def detect_batch_attendance(self, attendance_records, time_window=60):
        """Detect if multiple attendances occurred in batch (in seconds)"""
        if len(attendance_records) < 2:
            return {'batch_detected': False}
        
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in attendance_records]
        
        # Sort timestamps
        timestamps.sort()
        
        # Find clusters
        clusters = []
        current_cluster = [timestamps[0]]
        
        for i in range(1, len(timestamps)):
            time_diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            
            if time_diff <= time_window:
                current_cluster.append(timestamps[i])
            else:
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [timestamps[i]]
        
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
        
        return {
            'batch_detected': len(clusters) > 0,
            'batch_count': len(clusters),
            'batch_details': [{
                'size': len(cluster),
                'start': cluster[0].isoformat(),
                'end': cluster[-1].isoformat()
            } for cluster in clusters]
        }