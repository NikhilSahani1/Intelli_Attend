# enroll_faces.py - Run this ONCE to fix face recognition
import sqlite3
import cv2
import os
import sys

# Add backend to path
sys.path.insert(0, r'c:\Users\NIKHIL\OneDrive\Desktop\AMS\backend')

# Import FaceRecognizerV2
from ml_models.face_recognizer_v2 import FaceRecognizerV2

# Database path
db_path = r'c:\Users\NIKHIL\OneDrive\Desktop\AMS\database\event_system.db'

# Initialize face recognizer
fr = FaceRecognizerV2(db_path=db_path)

# Path to face photos
faces_dir = r'c:\Users\NIKHIL\OneDrive\Desktop\AMS\frontend\static\faces'

print("=" * 60)
print("Starting Face Enrollment Process")
print("=" * 60)

enrolled = 0
failed = 0
users_without_faces = 0

# Get all users from database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
users = cursor.execute('SELECT id, name FROM users WHERE role = "user"').fetchall()
print(f"Found {len(users)} users in database\n")

for user_id, user_name in users:
    user_dir = os.path.join(faces_dir, str(user_id))
    
    if os.path.exists(user_dir):
        # Get all face images for this user
        face_files = [f for f in os.listdir(user_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        
        if face_files:
            # Use the first face image
            face_path = os.path.join(user_dir, face_files[0])
            img = cv2.imread(face_path)
            
            if img is not None:
                # Detect face in the image
                faces = fr.detect_faces(img)
                
                if faces and len(faces) > 0:
                    face_roi = faces[0]['face']
                    success, message = fr.enroll_face(int(user_id), face_roi)
                    
                    if success:
                        enrolled += 1
                        print(f"✅ Enrolled: {user_name} (ID: {user_id})")
                    else:
                        failed += 1
                        print(f"❌ Failed: {user_name} - {message}")
                else:
                    failed += 1
                    print(f"⚠️ No face detected in photo: {user_name} (ID: {user_id})")
            else:
                failed += 1
                print(f"❌ Could not load image: {user_name} (ID: {user_id})")
        else:
            users_without_faces += 1
            print(f"📷 No face photos: {user_name} (ID: {user_id})")
    else:
        users_without_faces += 1
        print(f"📁 No face directory: {user_name} (ID: {user_id})")

conn.close()

print("\n" + "=" * 60)
print("ENROLLMENT COMPLETE")
print("=" * 60)
print(f"✅ Successfully enrolled: {enrolled} users")
print(f"❌ Failed to enroll: {failed} users")
print(f"📷 No face photos: {users_without_faces} users")
print("=" * 60)

# Verify enrollment
conn = sqlite3.connect(db_path)
count = conn.execute('SELECT COUNT(*) FROM face_data_final').fetchone()[0]
print(f"\n📊 Total embeddings in database: {count}")
conn.close()

if count > 0:
    print("\n✅ SUCCESS! Face recognition should now work!")
    print("   Restart your Flask server and test again.")
else:
    print("\n❌ ERROR: No embeddings were saved to database!")
    print("   Check if the face_data_final table was created.")