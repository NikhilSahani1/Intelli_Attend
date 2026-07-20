import sqlite3
import cv2
import os
import sys
import numpy as np

# Add backend to path
sys.path.insert(0, r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\backend')

# Import the simple face recognizer
from ml_models.face_recognizer_simple import SimpleFaceRecognizer

db_path = r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\database\event_system.db'
faces_dir = r'C:\Users\NIKHIL\OneDrive\Desktop\AMS\frontend\static\faces'

print("=" * 60)
print("Starting Face Enrollment Process")
print("=" * 60)

# Initialize recognizer
fr = SimpleFaceRecognizer(db_path=db_path)

enrolled = 0
failed = 0
no_face = 0

for user_id in os.listdir(faces_dir):
    user_dir = os.path.join(faces_dir, user_id)
    if os.path.isdir(user_dir):
        # Find face images
        face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        
        if face_files:
            # Use the first face image
            img_path = os.path.join(user_dir, face_files[0])
            img = cv2.imread(img_path)
            
            if img is not None:
                # Detect face
                faces = fr.detect_faces(img)
                
                if faces and len(faces) > 0:
                    # Enroll the face
                    face_roi = faces[0]['face']
                    success, message = fr.enroll_face(int(user_id), face_roi)
                    
                    if success:
                        enrolled += 1
                        print(f"✅ Enrolled user ID: {user_id}")
                    else:
                        failed += 1
                        print(f"❌ Failed user {user_id}: {message}")
                else:
                    no_face += 1
                    print(f"⚠️ No face detected for user {user_id}")
            else:
                failed += 1
                print(f"❌ Could not load image for user {user_id}")
        else:
            no_face += 1
            print(f"📁 No face photos for user {user_id}")

print("\n" + "=" * 60)
print("ENROLLMENT COMPLETE")
print("=" * 60)
print(f"✅ Successfully enrolled: {enrolled} users")
print(f"❌ Failed: {failed} users")
print(f"📷 No face photos: {no_face} users")
print("=" * 60)

# Verify
conn = sqlite3.connect(db_path)
count = conn.execute('SELECT COUNT(*) FROM face_data_simple').fetchone()[0]
print(f"\n📊 Total face embeddings in database: {count}")
conn.close()

if count > 0:
    print("\n🎉 SUCCESS! Face recognition will now work!")
    print("   Restart your Flask server and test again.")
else:
    print("\n❌ ERROR: No embeddings were saved!")