import sqlite3
import cv2
import os
import sys

sys.path.insert(0, r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\backend')
from ml_models.face_recognizer_simple import SimpleFaceRecognizer

db_path = r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\database\event_system.db'
fr = SimpleFaceRecognizer(db_path=db_path)
faces_dir = r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\frontend\static\faces'

print("=" * 50)
print("Enrolling faces from existing photos...")
print("=" * 50)

enrolled = 0
for user_id in os.listdir(faces_dir):
    user_dir = os.path.join(faces_dir, user_id)
    if os.path.isdir(user_dir):
        face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        if face_files:
            img = cv2.imread(os.path.join(user_dir, face_files[0]))
            if img is not None:
                faces = fr.detect_faces(img)
                if faces:
                    success, msg = fr.enroll_face(int(user_id), faces[0]['face'])
                    if success:
                        enrolled += 1
                        print(f"✅ Enrolled user {user_id}")
                    else:
                        print(f"❌ Failed user {user_id}: {msg}")
                else:
                    print(f"⚠️ No face detected for user {user_id}")
            else:
                print(f"⚠️ Could not load image for user {user_id}")

print(f"\n✅ Enrolled {enrolled} users!")
print("\nNow restart your Flask server and test face recognition!")