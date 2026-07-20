import cv2
import numpy as np
import pickle
import os
import sqlite3

class SimpleFaceRecognizer:
    def __init__(self, db_path=None):
        print("🔧 Initializing Simple Face Recognizer")
        
        # Load OpenCV face detector
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        self.db_path = db_path
        self.embeddings_cache = {}
        
        if db_path and os.path.exists(db_path):
            self._load_embeddings()
        
        print("✅ Simple Face Recognizer Ready")
    
    def detect_faces(self, image):
        """Detect faces using OpenCV"""
        if image is None:
            return []
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            
            results = []
            for (x, y, w, h) in faces:
                # Add padding
                pad_x = int(w * 0.15)
                pad_y = int(h * 0.15)
                x = max(0, x - pad_x)
                y = max(0, y - pad_y)
                w = min(image.shape[1] - x, w + 2 * pad_x)
                h = min(image.shape[0] - y, h + 2 * pad_y)
                
                face_roi = image[y:y+h, x:x+w]
                if face_roi.size > 0:
                    face_roi = cv2.resize(face_roi, (100, 100))
                    results.append({
                        'box': (x, y, w, h),
                        'face': face_roi,
                        'confidence': 1.0
                    })
            
            return results
        except Exception as e:
            print(f"Detection error: {e}")
            return []
    
    def create_embedding(self, face_img):
        """Create simple embedding"""
        try:
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (100, 100))
            embedding = gray.flatten() / 255.0
            return embedding
        except:
            return None
    
    def compare_faces(self, emb1, emb2, threshold=0.68):
        if emb1 is None or emb2 is None:
            return False, 0
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-8)
        return similarity > threshold, similarity * 100
    
    def recognize_face(self, face_img, threshold=0.68):
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
                user = conn.execute('SELECT name FROM users WHERE id = ?', (best_id,)).fetchone()
                conn.close()
                if user:
                    return best_id, user[0], best_sim, best_sim
            
            return None, None, 0, 0
        except Exception as e:
            print(f"Recognition error: {e}")
            return None, None, 0, 0
    
    def recognize_face_with_voting(self, face_img, threshold=0.68):
        user_id, user_name, similarity, _ = self.recognize_face(face_img, threshold)
        return user_id, similarity, user_name
    
    def recognize(self, face_img, threshold=0.68):
        user_id, user_name, similarity, _ = self.recognize_face(face_img, threshold)
        if user_id:
            return [{'user_id': user_id, 'user_name': user_name, 'confidence': similarity}]
        return []
    
    def predict(self, face_img, threshold=0.68):
        user_id, user_name, similarity, _ = self.recognize_face(face_img, threshold)
        return user_id, similarity
    
    def enroll_face(self, user_id, face_img):
        try:
            emb = self.create_embedding(face_img)
            if emb is None:
                return False, "Could not create embedding"
            
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS face_data_simple (
                    user_id INTEGER PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('INSERT OR REPLACE INTO face_data_simple (user_id, embedding) VALUES (?, ?)',
                        (user_id, pickle.dumps(emb)))
            conn.execute('UPDATE users SET face_enrolled = 1 WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            self.embeddings_cache[user_id] = emb
            return True, "Face enrolled"
        except Exception as e:
            return False, str(e)
    
    def _load_embeddings(self):
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='face_data_simple'")
            if cursor.fetchone():
                rows = cursor.execute('SELECT user_id, embedding FROM face_data_simple').fetchall()
                for uid, blob in rows:
                    self.embeddings_cache[uid] = pickle.loads(blob)
                print(f"✅ Loaded {len(self.embeddings_cache)} faces")
            conn.close()
        except Exception as e:
            print(f"Load error: {e}")
    
    def get_stats(self):
        return {'enrolled_users': len(self.embeddings_cache), 'version': 'simple'}