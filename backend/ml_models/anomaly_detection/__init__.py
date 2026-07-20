"""
Anomaly Detection Module for AMS
Detects unusual patterns in attendance and user behavior
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import pandas as pd
import json
import os

class AnomalyDetector:
    """
    Anomaly Detection for AMS
    Uses Isolation Forest for detecting unusual patterns
    """
    
    def __init__(self, contamination=0.1):
        """
        Initialize Anomaly Detector
        
        Args:
            contamination: Expected proportion of outliers
        """
        self.model = IsolationForest(contamination=contamination, random_state=42)
        self.scaler = StandardScaler()
        self.is_trained = False
        self.stats = {
            'total_analyzed': 0,
            'anomalies_detected': 0,
            'last_training': None
        }
        
        # Load existing model if available
        self.load_model()
    
    def prepare_features(self, attendance_data):
        """
        Prepare features for anomaly detection
        
        Args:
            attendance_data: List of attendance records
            
        Returns:
            Feature matrix
        """
        features = []
        
        for record in attendance_data:
            # Extract features
            features.append([
                record.get('fraud_score', 0),  # Fraud score
                self._get_hour_value(record.get('timestamp')),  # Hour of day
                self._get_day_value(record.get('timestamp')),  # Day of week
                record.get('attendance_count', 1),  # User's attendance count
                1 if record.get('face_verified', False) else 0,  # Face verification
                record.get('time_diff', 0)  # Time difference from normal
            ])
        
        return np.array(features)
    
    def train(self, attendance_data):
        """
        Train the anomaly detection model
        
        Args:
            attendance_data: List of attendance records
        """
        if len(attendance_data) < 10:
            return False
        
        features = self.prepare_features(attendance_data)
        
        if len(features) > 0:
            # Scale features
            features_scaled = self.scaler.fit_transform(features)
            
            # Train model
            self.model.fit(features_scaled)
            self.is_trained = True
            self.stats['last_training'] = datetime.now().isoformat()
            self.stats['total_analyzed'] = len(attendance_data)
            
            # Save model
            self.save_model()
            return True
        
        return False
    
    def detect(self, record):
        """
        Detect if a single record is anomalous
        
        Args:
            record: Single attendance record
            
        Returns:
            (is_anomaly, anomaly_score)
        """
        if not self.is_trained:
            return False, 0.0
        
        try:
            features = self.prepare_features([record])
            features_scaled = self.scaler.transform(features)
            
            # Predict (-1 for anomaly, 1 for normal)
            prediction = self.model.predict(features_scaled)[0]
            score = self.model.score_samples(features_scaled)[0]
            
            is_anomaly = prediction == -1
            anomaly_score = abs(score)
            
            if is_anomaly:
                self.stats['anomalies_detected'] += 1
            
            return is_anomaly, anomaly_score
            
        except Exception as e:
            print(f"Error in detection: {e}")
            return False, 0.0
    
    def detect_batch(self, attendance_data):
        """
        Detect anomalies in batch of records
        
        Args:
            attendance_data: List of attendance records
            
        Returns:
            List of records with anomaly flags
        """
        if not self.is_trained or len(attendance_data) == 0:
            return [(record, False, 0.0) for record in attendance_data]
        
        try:
            features = self.prepare_features(attendance_data)
            features_scaled = self.scaler.transform(features)
            
            predictions = self.model.predict(features_scaled)
            scores = self.model.score_samples(features_scaled)
            
            results = []
            for i, record in enumerate(attendance_data):
                is_anomaly = predictions[i] == -1
                anomaly_score = abs(scores[i])
                
                if is_anomaly:
                    self.stats['anomalies_detected'] += 1
                
                results.append((record, is_anomaly, anomaly_score))
            
            self.stats['total_analyzed'] += len(attendance_data)
            return results
            
        except Exception as e:
            print(f"Error in batch detection: {e}")
            return [(record, False, 0.0) for record in attendance_data]
    
    def detect_all(self, attendance_data):
        """
        Comprehensive anomaly detection with analysis
        
        Args:
            attendance_data: List of attendance records
            
        Returns:
            Dictionary with detailed anomaly analysis
        """
        if not self.is_trained and len(attendance_data) >= 10:
            self.train(attendance_data)
        
        results = self.detect_batch(attendance_data)
        
        # Analyze by category
        anomalies = []
        high_risk_users = {}
        
        for record, is_anomaly, score in results:
            if is_anomaly:
                anomaly_info = {
                    'user_id': record.get('user_id'),
                    'user_name': record.get('user_name'),
                    'event_name': record.get('event_name'),
                    'timestamp': record.get('timestamp'),
                    'fraud_score': record.get('fraud_score'),
                    'anomaly_score': score,
                    'type': self._classify_anomaly(record, score)
                }
                anomalies.append(anomaly_info)
                
                # Track high-risk users
                user_id = record.get('user_id')
                if user_id:
                    if user_id not in high_risk_users:
                        high_risk_users[user_id] = {
                            'count': 0,
                            'max_score': 0,
                            'records': []
                        }
                    high_risk_users[user_id]['count'] += 1
                    high_risk_users[user_id]['max_score'] = max(
                        high_risk_users[user_id]['max_score'], score
                    )
                    high_risk_users[user_id]['records'].append(anomaly_info)
        
        return {
            'anomalies': anomalies,
            'total_analyzed': len(attendance_data),
            'anomaly_count': len(anomalies),
            'anomaly_rate': len(anomalies) / len(attendance_data) if attendance_data else 0,
            'high_risk_users': high_risk_users,
            'stats': self.stats
        }
    
    def _get_hour_value(self, timestamp):
        """Extract hour from timestamp"""
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.hour
                except:
                    pass
        return 12  # Default hour
    
    def _get_day_value(self, timestamp):
        """Extract day of week from timestamp"""
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.weekday()
                except:
                    pass
        return 0  # Default Monday
    
    def _classify_anomaly(self, record, score):
        """Classify the type of anomaly"""
        fraud_score = record.get('fraud_score', 0)
        
        if fraud_score > 0.8:
            return 'CRITICAL_FRAUD'
        elif fraud_score > 0.6:
            return 'HIGH_FRAUD'
        elif score > 0.7:
            return 'UNUSUAL_PATTERN'
        else:
            return 'MINOR_ANOMALY'
    
    def save_model(self):
        """Save the trained model"""
        try:
            import joblib
            
            model_dir = os.path.join('ml_models', 'saved_models')
            os.makedirs(model_dir, exist_ok=True)
            
            model_path = os.path.join(model_dir, 'anomaly_detector.pkl')
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler,
                'is_trained': self.is_trained,
                'stats': self.stats
            }, model_path)
            
        except Exception as e:
            print(f"Error saving anomaly detector: {e}")
    
    def load_model(self):
        """Load saved model"""
        try:
            import joblib
            
            model_path = os.path.join('ml_models', 'saved_models', 'anomaly_detector.pkl')
            if os.path.exists(model_path):
                data = joblib.load(model_path)
                self.model = data['model']
                self.scaler = data['scaler']
                self.is_trained = data['is_trained']
                self.stats = data.get('stats', self.stats)
                
        except Exception as e:
            print(f"Error loading anomaly detector: {e}")