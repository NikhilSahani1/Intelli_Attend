# Create a new file: backend/train_face_enhanced.py
import cv2
import os
import pickle
import numpy as np

def retrain_face_model():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(backend_dir)
    faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')
    
    print(f"Looking for faces in: {faces_base_dir}")
    
    # Get all users with face directories
    faces = []
    labels = []
    label_names = {}
    
    for user_id in os.listdir(faces_base_dir):
        user_dir = os.path.join(faces_base_dir, user_id)
        if os.path.isdir(user_dir):
            # Get user name from database or use folder name
            face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
            print(f"User {user_id}: {len(face_files)} face images")
            
            for face_file in face_files:
                face_path = os.path.join(user_dir, face_file)
                face_img = cv2.imread(face_path, cv2.IMREAD_GRAYSCALE)
                
                if face_img is not None:
                    # Resize and enhance
                    face_img = cv2.resize(face_img, (100, 100))
                    # Apply histogram equalization for better contrast
                    face_img = cv2.equalizeHist(face_img)
                    faces.append(face_img)
                    labels.append(int(user_id))
                    label_names[int(user_id)] = f"User_{user_id}"
                    print(f"  Loaded: {face_file}")
    
    if len(faces) == 0:
        print("No faces found!")
        return
    
    print(f"\nTraining with {len(faces)} face images from {len(label_names)} users")
    
    # Create recognizer
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        print("Created LBPHFaceRecognizer")
    except:
        recognizer = cv2.face_LBPHFaceRecognizer.create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        print("Created LBPHFaceRecognizer (alternate)")
    
    # Train
    recognizer.train(faces, np.array(labels))
    
    # Save model
    model_dir = os.path.join(backend_dir, 'ml_models', 'saved_models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'face_recognizer.yml')
    recognizer.save(model_path)
    
    labels_path = os.path.join(model_dir, 'face_labels.pkl')
    with open(labels_path, 'wb') as f:
        pickle.dump(label_names, f)
    
    print(f"✅ Model saved to: {model_path}")
    print(f"✅ Labels saved to: {labels_path}")

if __name__ == '__main__':
    retrain_face_model()