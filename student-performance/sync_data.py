import csv
import sys
sys.path.append('.')
from db import get_db_connection

def sync_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Upload Students (if missing)
    with open('students.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no=%s", (row['enrollment_no'],))
            if not cursor.fetchone():
                email = f"{row['enrollment_no']}@spda.edu"
                from werkzeug.security import generate_password_hash
                pw = generate_password_hash(row['enrollment_no'] + "@123")
                cursor.execute("""
                    INSERT INTO students (name, enrollment_no, email, department, semester, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (row['name'], row['enrollment_no'], email, row['department'], row['semester'], pw))
    
    # 2. Upload Subjects (if missing)
    with open('subjects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_name=%s AND department=%s AND semester=%s", 
                           (row['subject_name'], row['department'], row['semester']))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO subjects (subject_name, department, semester) VALUES (%s, %s, %s)", 
                               (row['subject_name'], row['department'], row['semester']))
    
    # 3. Upload Attendance
    with open('attendance.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            cursor.execute("""
                SELECT subject_id FROM subjects 
                WHERE subject_name=%s AND department=%s AND semester=%s
            """, (row['subject'], row['department'], row['semester']))
            sub = cursor.fetchone()
            if not sub: continue
            sub_id = sub[0]
            
            cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no=%s AND subject_id=%s AND date=%s", 
                           (row['enrollment_no'], sub_id, row['date']))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)", 
                               (row['enrollment_no'], sub_id, row['date'], row['status']))
                count += 1
                if count % 1000 == 0:
                    conn.commit()
                    print(f"Uploaded {count} attendance records...")
        
    conn.commit()
    conn.close()
    print("Sync complete!")

if __name__ == "__main__":
    sync_data()
