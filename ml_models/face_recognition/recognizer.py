"""
Face Recognition for user verification and attendance
"""
import os
import cv2
import numpy as np
import face_recognition
import pickle
from datetime import datetime
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ml_models import MLModelBase

class FaceRecognizer(MLModelBase):
    """Face recognition for user identification"""
    
    def __init__(self):
        super().__init__('face_recognition')
        self.known_face_encodings = []
        self.known_face_ids = []
        self.known_face_names = []
        self.encoding_file = os.path.join(self.model_path, 'face_encodings.pkl')
        
        # Load existing encodings if available
        self.load_encodings()
    
    def load_encodings(self):
        """Load saved face encodings"""
        if os.path.exists(self.encoding_file):
            try:
                with open(self.encoding_file, 'rb') as f:
                    data = pickle.load(f)
                    self.known_face_encodings = data.get('encodings', [])
                    self.known_face_ids = data.get('ids', [])
                    self.known_face_names = data.get('names', [])
                    self.metadata = data.get('metadata', {})
                return True
            except:
                return False
        return False
    
    def save_encodings(self):
        """Save face encodings to disk"""
        data = {
            'encodings': self.known_face_encodings,
            'ids': self.known_face_ids,
            'names': self.known_face_names,
            'metadata': {
                **self.metadata,
                'updated_at': datetime.now().isoformat(),
                'n_faces': len(self.known_face_encodings)
            }
        }
        with open(self.encoding_file, 'wb') as f:
            pickle.dump(data, f)
        return True
    
    def encode_face(self, image_path):
        """
        Extract face encoding from an image
        
        Parameters:
        - image_path: Path to the image file
        
        Returns:
        - Face encoding (128-dim vector) or None if no face detected
        """
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Detect face locations
            face_locations = face_recognition.face_locations(image)
            
            if len(face_locations) == 0:
                return None
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if len(face_encodings) > 0:
                return face_encodings[0]
            
            return None
            
        except Exception as e:
            print(f"Error encoding face: {e}")
            return None
    
    def add_face(self, user_id, user_name, image_path):
        """
        Add a new face to the database
        
        Parameters:
        - user_id: User ID
        - user_name: User name
        - image_path: Path to face image
        
        Returns:
        - Success status
        """
        encoding = self.encode_face(image_path)
        
        if encoding is None:
            return False, "No face detected in image"
        
        # Check if user already exists
        if user_id in self.known_face_ids:
            # Update existing
            idx = self.known_face_ids.index(user_id)
            self.known_face_encodings[idx] = encoding
            self.known_face_names[idx] = user_name
        else:
            # Add new
            self.known_face_encodings.append(encoding)
            self.known_face_ids.append(user_id)
            self.known_face_names.append(user_name)
        
        # Save to disk
        self.save_encodings()
        
        return True, "Face added successfully"
    
    def recognize(self, image_path, tolerance=0.6):
        """
        Recognize faces in an image
        
        Parameters:
        - image_path: Path to image file
        - tolerance: Face match tolerance (lower = stricter)
        
        Returns:
        - List of recognized users with confidence
        """
        if len(self.known_face_encodings) == 0:
            return []
        
        try:
            # Load image
            image = face_recognition.load_image_file(image_path)
            
            # Detect faces
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            results = []
            
            for i, face_encoding in enumerate(face_encodings):
                # Compare with known faces
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, 
                    face_encoding, 
                    tolerance=tolerance
                )
                
                # Calculate face distances
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings, 
                    face_encoding
                )
                
                if True in matches:
                    # Get best match
                    best_match_index = np.argmin(face_distances)
                    confidence = 1 - face_distances[best_match_index]
                    
                    results.append({
                        'user_id': self.known_face_ids[best_match_index],
                        'user_name': self.known_face_names[best_match_index],
                        'confidence': float(confidence),
                        'location': face_locations[i] if i < len(face_locations) else None
                    })
                else:
                    # Unknown face
                    results.append({
                        'user_id': None,
                        'user_name': 'Unknown',
                        'confidence': float(1 - np.min(face_distances)) if len(face_distances) > 0 else 0,
                        'location': face_locations[i] if i < len(face_locations) else None
                    })
            
            return results
            
        except Exception as e:
            print(f"Error in face recognition: {e}")
            return []
    
    def verify_face(self, user_id, image_path, tolerance=0.6):
        """
        Verify if the face in image matches a specific user
        
        Returns:
        - Boolean indicating match
        - Confidence score
        """
        if user_id not in self.known_face_ids:
            return False, 0.0
        
        idx = self.known_face_ids.index(user_id)
        known_encoding = self.known_face_encodings[idx]
        
        try:
            # Load and encode new image
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)
            
            if len(face_locations) == 0:
                return False, 0.0
            
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if len(face_encodings) == 0:
                return False, 0.0
            
            # Compare
            face_distance = face_recognition.face_distance([known_encoding], face_encodings[0])[0]
            
            is_match = face_distance <= tolerance
            confidence = 1 - face_distance
            
            return is_match, float(confidence)
            
        except Exception as e:
            print(f"Error in face verification: {e}")
            return False, 0.0
    
    def get_stats(self):
        """Get statistics about the face database"""
        return {
            'total_faces': len(self.known_face_encodings),
            'users': len(set(self.known_face_ids)),
            'updated_at': self.metadata.get('updated_at', 'Never'),
            'encoding_dim': 128 if self.known_face_encodings else 0
        }