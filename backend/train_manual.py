import cv2
import numpy as np
import os
import pickle
import sqlite3

# Database path
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'event_system.db')

# Get all users with enrolled faces
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

users = cursor.execute('SELECT id, name FROM users WHERE face_enrolled = 1').fetchall()

faces = []
labels = []
label_names = {}

backend_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(backend_dir)
faces_base_dir = os.path.join(project_dir, 'frontend', 'static', 'faces')

for user in users:
    user_id = user['id']
    user_name = user['name']
    user_dir = os.path.join(faces_base_dir, str(user_id))
    
    if os.path.exists(user_dir):
        for img_file in os.listdir(user_dir):
            if img_file.endswith(('.jpg', '.png', '.jpeg')):
                img_path = os.path.join(user_dir, img_file)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img = cv2.resize(img, (100, 100))
                    faces.append(img)
                    labels.append(user_id)
                    label_names[user_id] = user_name
                    print(f"Loaded: {img_file} for {user_name}")

conn.close()

if len(faces) == 0:
    print("No faces found!")
    exit()

print(f"Training with {len(faces)} faces from {len(label_names)} users")

try:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
except:
    recognizer = cv2.face_LBPHFaceRecognizer.create()

recognizer.train(faces, np.array(labels))

model_dir = os.path.join(backend_dir, 'ml_models', 'saved_models')
os.makedirs(model_dir, exist_ok=True)
recognizer.save(os.path.join(model_dir, 'face_recognizer.yml'))

with open(os.path.join(model_dir, 'face_labels.pkl'), 'wb') as f:
    pickle.dump(label_names, f)

print("✅ Model trained successfully!")