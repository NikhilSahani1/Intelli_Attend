"""
Attendance Prediction Module for AMS
Predicts future attendance patterns and user behavior
"""
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from datetime import datetime, timedelta
import pandas as pd
import joblib
import os

class AttendancePredictor:
    """
    Predicts attendance patterns and user engagement
    """
    
    def __init__(self):
        """Initialize predictor models"""
        self.daily_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.user_model = LinearRegression()
        self.is_trained = False
        
        self.load_model()
    
    def train_daily_attendance(self, historical_data):
        """
        Train model to predict daily attendance
        
        Args:
            historical_data: List of daily attendance counts with features
        """
        if len(historical_data) < 7:  # Need at least a week of data
            return False
        
        # Prepare features
        X = []
        y = []
        
        for i in range(len(historical_data) - 1):
            features = []
            
            # Day of week (0-6)
            features.append(historical_data[i]['day_of_week'])
            
            # Previous day attendance
            features.append(historical_data[i]['attendance_count'])
            
            # Day of month
            features.append(historical_data[i]['day_of_month'])
            
            # Is weekend?
            features.append(1 if historical_data[i]['day_of_week'] in [5, 6] else 0)
            
            # Previous 7-day average
            week_avg = np.mean([d['attendance_count'] for d in historical_data[max(0, i-7):i]])
            features.append(week_avg)
            
            X.append(features)
            y.append(historical_data[i+1]['attendance_count'])
        
        if len(X) > 0:
            self.daily_model.fit(X, y)
            self.is_trained = True
            self.save_model()
            return True
        
        return False
    
    def predict_daily_attendance(self, features):
        """
        Predict attendance for a given day
        
        Args:
            features: Dictionary with day features
            
        Returns:
            Predicted attendance count
        """
        if not self.is_trained:
            return 0
        
        try:
            feature_vector = [
                features.get('day_of_week', 0),
                features.get('prev_attendance', 0),
                features.get('day_of_month', 1),
                features.get('is_weekend', 0),
                features.get('week_avg', 0)
            ]
            
            prediction = self.daily_model.predict([feature_vector])[0]
            return max(0, int(prediction))
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            return 0
    
    def predict_user_attendance(self, user_history):
        """
        Predict future attendance for a specific user
        
        Args:
            user_history: List of user attendance records
            
        Returns:
            Predicted attendance rate for next 30 days
        """
        if len(user_history) < 3:
            return 0.5  # Default prediction
        
        # Prepare time series
        days = list(range(len(user_history)))
        attendance_counts = [h['count'] for h in user_history]
        
        # Linear regression for trend
        X = np.array(days).reshape(-1, 1)
        y = np.array(attendance_counts)
        
        self.user_model.fit(X, y)
        
        # Predict next 30 days
        future_days = np.array([len(user_history) + i for i in range(30)]).reshape(-1, 1)
        future_predictions = self.user_model.predict(future_days)
        
        # Average predicted daily attendance
        avg_prediction = np.mean(future_predictions)
        
        return min(1.0, max(0.0, avg_prediction / 30))  # Normalize to rate
    
    def get_attendance_trend(self, attendance_data):
        """
        Analyze attendance trend
        
        Args:
            attendance_data: List of attendance records
            
        Returns:
            Dictionary with trend analysis
        """
        if len(attendance_data) < 2:
            return {
                'trend': 'insufficient_data',
                'growth_rate': 0,
                'predicted_next_week': 0
            }
        
        # Group by date
        daily_counts = {}
        for record in attendance_data:
            date = record.get('date', datetime.now().strftime('%Y-%m-%d'))
            daily_counts[date] = daily_counts.get(date, 0) + 1
        
        # Sort by date
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[date] for date in dates]
        
        if len(counts) >= 2:
            # Calculate trend
            X = np.array(range(len(counts))).reshape(-1, 1)
            y = np.array(counts)
            
            model = LinearRegression()
            model.fit(X, y)
            
            trend = model.coef_[0]
            growth_rate = (trend / np.mean(counts)) * 100 if np.mean(counts) > 0 else 0
            
            # Predict next week
            next_week = model.predict([[len(counts) + 7]])[0]
            
            return {
                'trend': 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
                'growth_rate': growth_rate,
                'predicted_next_week': max(0, int(next_week)),
                'average_attendance': np.mean(counts),
                'peak_attendance': max(counts),
                'trend_strength': abs(trend)
            }
        
        return {
            'trend': 'stable',
            'growth_rate': 0,
            'predicted_next_week': 0
        }
    
    def save_model(self):
        """Save trained models"""
        try:
            model_dir = os.path.join('ml_models', 'saved_models')
            os.makedirs(model_dir, exist_ok=True)
            
            # Save daily prediction model
            daily_path = os.path.join(model_dir, 'daily_predictor.pkl')
            joblib.dump(self.daily_model, daily_path)
            
            # Save user model
            user_path = os.path.join(model_dir, 'user_predictor.pkl')
            joblib.dump(self.user_model, user_path)
            
        except Exception as e:
            print(f"Error saving predictor: {e}")
    
    def load_model(self):
        """Load saved models"""
        try:
            model_dir = os.path.join('ml_models', 'saved_models')
            
            daily_path = os.path.join(model_dir, 'daily_predictor.pkl')
            if os.path.exists(daily_path):
                self.daily_model = joblib.load(daily_path)
                self.is_trained = True
            
            user_path = os.path.join(model_dir, 'user_predictor.pkl')
            if os.path.exists(user_path):
                self.user_model = joblib.load(user_path)
                
        except Exception as e:
            print(f"Error loading predictor: {e}")