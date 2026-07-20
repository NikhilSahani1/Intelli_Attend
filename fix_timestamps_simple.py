import sqlite3
from datetime import datetime, timedelta

print("=" * 50)
print("Fixing Attendance Timestamps")
print("=" * 50)

# Connect to database
conn = sqlite3.connect('database/event_system.db')
cursor = conn.cursor()

# Show current records
print("\n📊 Current attendance records:")
cursor.execute("SELECT id, timestamp, fraud_score FROM attendance ORDER BY id")
records = cursor.fetchall()
for record in records:
    print(f"   ID: {record[0]}, Time: {record[1]}, Fraud: {record[2]}")

# Fix timestamps - Add 5 hours 30 minutes (UTC to IST)
print("\n🕐 Fixing timestamps...")
ist_offset = timedelta(hours=5, minutes=30)
fixed_count = 0

for record in records:
    record_id = record[0]
    old_time = record[1]
    
    if old_time:
        try:
            # Parse the timestamp
            dt = datetime.strptime(old_time, '%Y-%m-%d %H:%M:%S')
            # Add IST offset
            new_dt = dt + ist_offset
            new_time = new_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Update
            cursor.execute("UPDATE attendance SET timestamp = ? WHERE id = ?", (new_time, record_id))
            fixed_count += 1
            print(f"   ID {record_id}: {old_time} → {new_time}")
        except Exception as e:
            print(f"   ID {record_id}: Error - {e}")

conn.commit()
print(f"\n✅ Fixed {fixed_count} records")

# Show updated records
print("\n📊 Updated attendance records:")
cursor.execute("SELECT id, timestamp, fraud_score FROM attendance ORDER BY timestamp DESC LIMIT 5")
for record in cursor.fetchall():
    print(f"   ID: {record[0]}, Time: {record[1]}, Fraud: {record[2]}")

conn.close()
print("\n✅ Done!")