import cv2
import numpy as np
import mediapipe as mp
import pickle
import os
import sqlite3

class FaceRecognizerV2:
    def __init__(self, db_path=None):
        print("🔧 Initializing FaceRecognizerV2 (Working Version)")
        
        self.face_detection = mp.solutions.face_detection.FaceDetection(
            model_selection=1, 
            min_detection_confidence=0.5
        )
        
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, 
            max_num_faces=10, 
            min_detection_confidence=0.5
        )
        
        self.db_path = db_path
        self.embeddings_cache = {}
        
        if db_path and os.path.exists(db_path):
            self._load_embeddings()
        
        print("✅ FaceRecognizerV2 Ready")
    
    def detect_faces(self, image):
        """RETURNS LIST OF DICTIONARIES - DEFINITIVE FIX"""
        if image is None:
            return []
        
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_detection.process(rgb)
            
            faces = []
            if results.detections:
                h, w = image.shape[:2]
                print(f"Found {len(results.detections)} detection(s)")
                
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    width = int(bbox.width * w)
                    height = int(bbox.height * h)
                    
                    # Add padding
                    pad_x = int(width * 0.15)
                    pad_y = int(height * 0.15)
                    x = max(0, x - pad_x)
                    y = max(0, y - pad_y)
                    width = min(w - x, width + 2 * pad_x)
                    height = min(h - y, height + 2 * pad_y)
                    
                    face_roi = image[y:y+height, x:x+width]
                    if face_roi.size > 0:
                        face_dict = {
                            'box': (x, y, width, height),
                            'face': face_roi,
                            'confidence': float(detection.score[0]) if detection.score else 1.0
                        }
                        faces.append(face_dict)
                        print(f"Added face: box={face_dict['box']}, confidence={face_dict['confidence']}")
            
            faces.sort(key=lambda f: f['confidence'], reverse=True)
            print(f"Returning {len(faces)} faces as dictionaries")
            return faces[:10]
            
        except Exception as e:
            print(f"Detection error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_features(self, face_img):
        """Extract 468 facial landmarks"""
        try:
            rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb)
            if results.multi_face_landmarks:
                features = []
                for lm in results.multi_face_landmarks[0].landmark:
                    features.extend([lm.x, lm.y, lm.z])
                return np.array(features)
            return None
        except Exception as e:
            return None
    
    def create_embedding(self, face_img):
        """Create normalized face embedding"""
        features = self.extract_features(face_img)
        if features is None:
            return None
        norm = np.linalg.norm(features)
        return features / norm if norm > 0 else features
    
    def compare_faces(self, emb1, emb2, threshold=0.68):
        """Compare two face embeddings using cosine similarity"""
        if emb1 is None or emb2 is None:
            return False, 0
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-8)
        return similarity > threshold, similarity * 100
    
    def recognize_face(self, face_img, threshold=0.68):
        """
        Recognize a face - MAIN RECOGNITION METHOD
        
        Args:
            face_img: Cropped face image (numpy array)
            threshold: Recognition threshold (0-1)
        
        Returns:
            tuple: (user_id, user_name, similarity_score, confidence)
        """
        try:
            emb = self.create_embedding(face_img)
            if emb is None:
                return None, None, 0, 0
            
            if not self.embeddings_cache:
                self._load_embeddings()
            
            if not self.embeddings_cache:
                return None, None, 0, 0
            
            best_id = None
            best_sim = 0
            
            for uid, uemb in self.embeddings_cache.items():
                is_match, similarity = self.compare_faces(emb, uemb, threshold)
                if is_match and similarity > best_sim:
                    best_sim = similarity
                    best_id = uid
            
            if best_id:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                user = cursor.execute('SELECT id, name FROM users WHERE id = ?', (best_id,)).fetchone()
                conn.close()
                if user:
                    return user[0], user[1], best_sim, best_sim
            
            return None, None, 0, 0
            
        except Exception as e:
            print(f"Recognition error: {e}")
            return None, None, 0, 0
    
    def predict(self, face_img, threshold=0.68):
        """Alias for recognize_face - returns (user_id, confidence)"""
        user_id, user_name, similarity, confidence = self.recognize_face(face_img, threshold)
        return user_id, similarity
    
    def recognize(self, face_img, threshold=0.68):
        """Alias for recognize_face - returns list of matches"""
        user_id, user_name, similarity, confidence = self.recognize_face(face_img, threshold)
        if user_id:
            return [{
                'user_id': user_id,
                'user_name': user_name,
                'confidence': similarity,
                'message': 'Recognized'
            }]
        return []
    
    def enroll_face(self, user_id, face_img):
        """Enroll a face"""
        try:
            emb = self.create_embedding(face_img)
            if emb is None:
                return False, "Could not detect face"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS face_data_final (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('INSERT OR REPLACE INTO face_data_final (user_id, embedding) VALUES (?, ?)',
                          (user_id, pickle.dumps(emb)))
            cursor.execute('UPDATE users SET face_enrolled = 1 WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            self.embeddings_cache[user_id] = emb
            return True, "Face enrolled successfully"
        except Exception as e:
            return False, str(e)
    
    def _load_embeddings(self):
        """Load embeddings from database"""
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='face_data_final'")
            if cursor.fetchone():
                rows = cursor.execute('SELECT user_id, embedding FROM face_data_final').fetchall()
                for uid, blob in rows:
                    self.embeddings_cache[uid] = pickle.loads(blob)
                print(f"✅ Loaded {len(self.embeddings_cache)} faces")
            conn.close()
        except Exception as e:
            print(f"Load error: {e}")
    
    def recognize_face_with_voting(self, face_img, threshold=0.68):
        """
        Alias for recognize_face that returns (user_id, confidence, user_name) format
        Used by some parts of the application
        """
        user_id, user_name, similarity, confidence = self.recognize_face(face_img, threshold)
        return user_id, similarity, user_name
    
    def get_stats(self):
        return {
            'enrolled_users': len(self.embeddings_cache),
            'max_faces_per_frame': 10,
            'version': 'v2_working'
        }