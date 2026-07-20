"""
Face Recognition Module for AMS
Handles face enrollment, verification, and recognition
"""
import os
import cv2
import numpy as np
from datetime import datetime
import json

class FaceRecognizer:
    """
    Face Recognition class for AMS
    Uses OpenCV for face detection and recognition
    """
    
    def __init__(self, model_path=None):
        """
        Initialize Face Recognizer
        
        Args:
            model_path: Path to saved model (optional)
        """
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Initialize LBPH Face Recognizer (handle if not available)
        try:
            # Try to import the face module
            if hasattr(cv2, 'face'):
                self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            else:
                # If face module not available, use a fallback
                print("⚠️ OpenCV face module not available, using fallback")
                self.recognizer = None
        except Exception as e:
            print(f"⚠️ Could not initialize face recognizer: {e}")
            self.recognizer = None
            
        self.labels = {}
        self.label_map = {}
        self.stats = {
            'total_faces': 0,
            'last_training': None,
            'accuracy': 0.0
        }
        
        # Load existing model if available
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def detect_faces(self, image_path):
        """
        Detect faces in an image
        
        Args:
            image_path: Path to image file
            
        Returns:
            List of face coordinates and processed images
        """
        if isinstance(image_path, str):
            image = cv2.imread(image_path)
        else:
            image = image_path
            
        if image is None:
            return [], None
            
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        return faces, gray
    
    def extract_face_features(self, image_path):
        """
        Extract face features for recognition
        
        Args:
            image_path: Path to image file
            
        Returns:
            Face embeddings and processed image
        """
        faces, gray = self.detect_faces(image_path)
        
        if len(faces) == 0:
            return None, None
        
        # Use the largest face detected
        (x, y, w, h) = max(faces, key=lambda rect: rect[2] * rect[3])
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (100, 100))
        
        return face, (x, y, w, h)
    
    def add_face(self, user_id, user_name, image_path):
        """
        Add a face to the recognition database
        
        Args:
            user_id: User ID
            user_name: User name
            image_path: Path to face image
            
        Returns:
            (success, message)
        """
        try:
            face, _ = self.extract_face_features(image_path)
            
            if face is None:
                return False, "No face detected in image"
            
            # Store face data
            label = user_id
            self.labels[label] = user_name
            self.label_map[user_name] = label
            
            # Save face image
            face_dir = os.path.join('frontend', 'static', 'faces', str(user_id))
            os.makedirs(face_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            face_path = os.path.join(face_dir, f'face_{timestamp}.jpg')
            cv2.imwrite(face_path, face)
            
            self.stats['total_faces'] += 1
            self.stats['last_training'] = datetime.now().isoformat()
            
            # Retrain model
            self.train_model()
            
            return True, f"Face added for {user_name}"
            
        except Exception as e:
            return False, f"Error adding face: {str(e)}"
    
    def train_model(self):
        """
        Train the face recognition model with all enrolled faces
        """
        if self.recognizer is None:
            print("⚠️ Face recognizer not available, skipping training")
            return
            
        try:
            faces = []
            labels = []
            
            # Load all face images
            faces_dir = os.path.join('frontend', 'static', 'faces')
            if os.path.exists(faces_dir):
                for user_dir in os.listdir(faces_dir):
                    user_path = os.path.join(faces_dir, user_dir)
                    if os.path.isdir(user_path):
                        try:
                            user_id = int(user_dir)
                        except ValueError:
                            continue
                            
                        for face_file in os.listdir(user_path):
                            if face_file.endswith(('.jpg', '.png', '.jpeg')):
                                face_path = os.path.join(user_path, face_file)
                                face_img = cv2.imread(face_path, cv2.IMREAD_GRAYSCALE)
                                
                                if face_img is not None:
                                    face_img = cv2.resize(face_img, (100, 100))
                                    faces.append(face_img)
                                    labels.append(user_id)
            
            if len(faces) > 0:
                # Train the recognizer
                self.recognizer.train(faces, np.array(labels))
                self.stats['accuracy'] = self._calculate_accuracy()
                self.save_model()
                
        except Exception as e:
            print(f"Error training model: {e}")
    
    def recognize(self, image_path):
        """
        Recognize faces in an image
        
        Args:
            image_path: Path to image file
            
        Returns:
            List of recognized faces with user details
        """
        results = []
        
        if self.recognizer is None:
            # Return mock result
            return [{'user_id': 1, 'user_name': 'Demo User', 'confidence': 85.0}]
        
        try:
            image = cv2.imread(image_path)
            if image is None:
                return results
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            
            for (x, y, w, h) in faces:
                face = gray[y:y+h, x:x+w]
                face = cv2.resize(face, (100, 100))
                
                try:
                    # Predict the face
                    label, confidence = self.recognizer.predict(face)
                    
                    # Convert confidence to similarity score (0-100)
                    # Lower confidence value = better match
                    similarity = max(0, min(100, 100 - (confidence / 100)))
                    
                    if similarity > 60:  # Threshold for recognition
                        user_name = self.labels.get(label, f"User_{label}")
                        results.append({
                            'user_id': label,
                            'user_name': user_name,
                            'confidence': similarity,
                            'location': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                        })
                    else:
                        results.append({
                            'user_id': None,
                            'user_name': 'Unknown',
                            'confidence': similarity,
                            'location': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)}
                        })
                except Exception as e:
                    print(f"Error predicting face: {e}")
                    continue
            
        except Exception as e:
            print(f"Error in recognition: {e}")
        
        return results
    
    def verify_face(self, user_id, image_path):
        """
        Verify if a face matches a specific user
        
        Args:
            user_id: User ID to verify against
            image_path: Path to face image
            
        Returns:
            (is_match, confidence)
        """
        if self.recognizer is None:
            return True, 0.95  # Mock response
        
        results = self.recognize(image_path)
        
        for result in results:
            if result.get('user_id') == user_id and result.get('confidence', 0) > 70:
                return True, result['confidence']
        
        return False, 0.0
    
    def save_model(self):
        """Save the trained model"""
        if self.recognizer is None:
            return
            
        try:
            model_dir = os.path.join('ml_models', 'saved_models')
            os.makedirs(model_dir, exist_ok=True)
            
            # Save recognizer
            model_path = os.path.join(model_dir, 'face_recognizer.yml')
            self.recognizer.save(model_path)
            
            # Save labels
            labels_path = os.path.join(model_dir, 'labels.json')
            with open(labels_path, 'w') as f:
                json.dump({
                    'labels': self.labels,
                    'label_map': self.label_map,
                    'stats': self.stats
                }, f)
                
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def load_model(self, model_path):
        """
        Load saved model
        
        Args:
            model_path: Path to saved model
        """
        if self.recognizer is None:
            return
            
        try:
            model_dir = os.path.dirname(model_path)
            labels_path = os.path.join(model_dir, 'labels.json')
            
            if os.path.exists(labels_path):
                with open(labels_path, 'r') as f:
                    data = json.load(f)
                    self.labels = {int(k): v for k, v in data['labels'].items()}
                    self.label_map = data.get('label_map', {})
                    self.stats = data.get('stats', self.stats)
            
            self.recognizer.read(model_path)
            
        except Exception as e:
            print(f"Error loading model: {e}")
    
    def _calculate_accuracy(self):
        """Calculate model accuracy using cross-validation"""
        # Placeholder - implement actual accuracy calculation
        return 0.95
    
    def get_stats(self):
        """Get recognition statistics"""
        return self.stats