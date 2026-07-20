"""
Model loading and management utilities
"""
import pickle
import os
import numpy as np
from datetime import datetime

class ModelLoader:
    """Load and manage ML models"""
    
    def __init__(self, models_path="frontend/static/trained_models/"):
        self.models_path = models_path
        os.makedirs(self.models_path, exist_ok=True)
        self.models = {}
        self.model_metadata = {}
    
    def save_model(self, model, model_name, metadata=None):
        """Save model to disk"""
        model_file = os.path.join(self.models_path, f"{model_name}.pkl")
        metadata_file = os.path.join(self.models_path, f"{model_name}_metadata.pkl")
        
        # Save model
        with open(model_file, 'wb') as f:
            pickle.dump(model, f)
        
        # Save metadata
        meta = {
            'name': model_name,
            'saved_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        with open(metadata_file, 'wb') as f:
            pickle.dump(meta, f)
        
        self.models[model_name] = model
        self.model_metadata[model_name] = meta
        
        return True
    
    def load_model(self, model_name):
        """Load model from disk"""
        if model_name in self.models:
            return self.models[model_name]
        
        model_file = os.path.join(self.models_path, f"{model_name}.pkl")
        metadata_file = os.path.join(self.models_path, f"{model_name}_metadata.pkl")
        
        if not os.path.exists(model_file):
            return None
        
        try:
            # Load model
            with open(model_file, 'rb') as f:
                model = pickle.load(f)
            
            # Load metadata
            if os.path.exists(metadata_file):
                with open(metadata_file, 'rb') as f:
                    metadata = pickle.load(f)
                    self.model_metadata[model_name] = metadata
            
            self.models[model_name] = model
            return model
            
        except Exception as e:
            print(f"Error loading model {model_name}: {e}")
            return None
    
    def list_models(self):
        """List all available models"""
        models = []
        
        for file in os.listdir(self.models_path):
            if file.endswith('.pkl') and not file.endswith('_metadata.pkl'):
                model_name = file[:-4]  # Remove .pkl
                
                # Get metadata
                metadata = self.model_metadata.get(model_name, {})
                
                models.append({
                    'name': model_name,
                    'file': file,
                    'saved_at': metadata.get('saved_at', 'Unknown')
                })
        
        return models
    
    def delete_model(self, model_name):
        """Delete model from disk"""
        model_file = os.path.join(self.models_path, f"{model_name}.pkl")
        metadata_file = os.path.join(self.models_path, f"{model_name}_metadata.pkl")
        
        deleted = False
        
        if os.path.exists(model_file):
            os.remove(model_file)
            deleted = True
        
        if os.path.exists(metadata_file):
            os.remove(metadata_file)
        
        if model_name in self.models:
            del self.models[model_name]
        
        if model_name in self.model_metadata:
            del self.model_metadata[model_name]
        
        return deleted
    
    def get_model_info(self, model_name):
        """Get model information"""
        model = self.load_model(model_name)
        
        if model is None:
            return None
        
        info = {
            'name': model_name,
            'type': type(model).__name__,
            'metadata': self.model_metadata.get(model_name, {})
        }
        
        # Add model-specific info
        if hasattr(model, 'get_params'):
            info['parameters'] = model.get_params()
        
        return info