"""
Utility functions for ML modules
"""
import numpy as np
import cv2
from datetime import datetime
import base64
import os

def preprocess_image(image_data):
    """
    Preprocess image for face recognition
    
    Args:
        image_data: Image file or base64 string
        
    Returns:
        Preprocessed image array
    """
    if isinstance(image_data, str):
        # Check if base64
        if image_data.startswith('data:image'):
            # Extract base64 data
            header, encoded = image_data.split(',', 1)
            image_data = base64.b64decode(encoded)
        
        # Read from bytes
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        # Assume it's already an image path or file object
        if hasattr(image_data, 'read'):
            # File object
            img = cv2.imdecode(np.frombuffer(image_data.read(), np.uint8), cv2.IMREAD_COLOR)
        else:
            # File path
            img = cv2.imread(image_data)
    
    if img is None:
        return None
    
    # Resize and normalize
    img = cv2.resize(img, (160, 160))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    
    return img

def extract_face_regions(image, faces):
    """
    Extract face regions from detected faces
    
    Args:
        image: Image array
        faces: List of face coordinates (x, y, w, h)
        
    Returns:
        List of extracted face regions
    """
    face_regions = []
    
    for (x, y, w, h) in faces:
        face = image[y:y+h, x:x+w]
        face_regions.append(face)
    
    return face_regions

def calculate_face_quality(face_image):
    """
    Calculate quality score for a face image
    
    Args:
        face_image: Face image array
        
    Returns:
        Quality score (0-100)
    """
    if face_image is None:
        return 0
    
    # Convert to grayscale
    if len(face_image.shape) == 3:
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = face_image
    
    # Calculate sharpness using Laplacian variance
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Normalize sharpness score (typical range 0-1000)
    sharpness_score = min(100, sharpness / 10)
    
    # Calculate brightness
    brightness = np.mean(gray)
    brightness_score = 100 - min(100, abs(brightness - 127))
    
    # Combine scores
    quality = (sharpness_score * 0.6 + brightness_score * 0.4)
    
    return min(100, max(0, quality))

def generate_face_embedding(face_image):
    """
    Generate face embedding for recognition
    
    Args:
        face_image: Face image array
        
    Returns:
        Face embedding vector
    """
    # Placeholder - in production, use a proper embedding model
    # For now, use simple HOG features
    if face_image is None:
        return np.zeros(128)
    
    # Resize to standard size
    face_resized = cv2.resize(face_image, (64, 64))
    
    # Convert to grayscale if needed
    if len(face_resized.shape) == 3:
        gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
    else:
        gray = face_resized
    
    # Compute HOG features (simplified)
    hog = cv2.HOGDescriptor()
    features = hog.compute(gray)
    
    # Flatten and normalize
    features = features.flatten()
    features = features / (np.linalg.norm(features) + 1e-6)
    
    # Pad or truncate to fixed size
    if len(features) < 128:
        features = np.pad(features, (0, 128 - len(features)))
    elif len(features) > 128:
        features = features[:128]
    
    return features

def evaluate_model_metrics(y_true, y_pred):
    """
    Evaluate model performance
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        Dictionary with metrics
    """
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    
    try:
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
            'f1_score': f1_score(y_true, y_pred, average='weighted', zero_division=0)
        }
        
        return metrics
        
    except Exception as e:
        print(f"Error evaluating metrics: {e}")
        return {
            'accuracy': 0,
            'precision': 0,
            'recall': 0,
            'f1_score': 0
        }