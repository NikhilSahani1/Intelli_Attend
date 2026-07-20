"""
Machine Learning Models for Intelligent Attendance System
"""
import os  
import json
import joblib
import numpy as np
from datetime import datetime

class MLModelBase:
    """Base class for all ML models"""
    
    def __init__(self, model_name, model_path=None):
        self.model_name = model_name
        self.model_path = model_path or os.path.join(os.path.dirname(__file__), 'saved_models')
        self.model = None
        self.metadata = {}
        
        # Create model directory if it doesn't exist
        os.makedirs(self.model_path, exist_ok=True)
    
    def save_model(self, filename):
        """Save model to disk"""
        if self.model:
            filepath = os.path.join(self.model_path, filename)
            joblib.dump(self.model, filepath)
            
            # Save metadata
            meta_path = filepath + '.json'
            with open(meta_path, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
            
            return filepath
        return None
    
    def load_model(self, filename):
        """Load model from disk"""
        filepath = os.path.join(self.model_path, filename)
        if os.path.exists(filepath):
            self.model = joblib.load(filepath)
            
            # Load metadata
            meta_path = filepath + '.json'
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    self.metadata = json.load(f)
            
            return True
        return False
    
    def preprocess(self, data):
        """Preprocess data - override in child classes"""
        return data
    
    def postprocess(self, predictions):
        """Postprocess predictions - override in child classes"""
        return predictions