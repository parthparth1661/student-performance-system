from db import get_db_connection
from werkzeug.security import generate_password_hash

def seed_database():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to SPDA.")
        return
        
    try:
        cursor = conn.cursor()
        
        # 0. Disable foreign key checks for clean truncation if needed
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        
        # Truncate tables to ensure fresh start (Optional but recommended for testing)
        tables = ['attendance', 'marks', 'subjects', 'students', 'faculty']
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        print("🌱 Seeding Starting...")

        # 1️⃣ INSERT STUDENTS 🧑🎓
        students_data = [
            ('101', 'Rahul', 'rahul@gmail.com', 'BCA', 1),
            ('102', 'Amit', 'amit@gmail.com', 'BCA', 2),
            ('103', 'Priya', 'priya@gmail.com', 'MCA', 1)
        ]
        
        for roll, name, email, dept, sem in students_data:
            pw_hash = generate_password_hash(f"{roll}@123")
            cursor.execute("""
                INSERT INTO students (enrollment_no, name, email, department, semester, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (roll, name, email, dept, sem, pw_hash))
        
        # 2️⃣ INSERT FACULTY 👨🏫
        faculty_data = [
            ('Dr. Sharma', 'sharma@gmail.com', 'BCA'),
            ('Dr. Mehta', 'mehta@gmail.com', 'MCA')
        ]
        cursor.executemany("""
            INSERT INTO faculty (faculty_name, email, department) VALUES (%s, %s, %s)
        """, faculty_data)
        
        # 3️⃣ INSERT SUBJECTS 📚
        # Note: faculty_id 1 is indexed from 1 usually in auto_increment
        subjects_data = [
            ('Python', 'BCA', 1, 1),
            ('DBMS', 'BCA', 2, 1),
            ('AI', 'MCA', 1, 2)
        ]
        cursor.executemany("""
            INSERT INTO subjects (subject_name, department, semester, faculty_id) VALUES (%s, %s, %s, %s)
        """, subjects_data)
        
        # 4️⃣ INSERT MARKS 📊
        # Schema: enrollment_no, subject_id, internal, viva, external, total
        marks_data = [
            ('101', 1, 25, 8, 42, 75),
            ('102', 2, 20, 5, 40, 65),
            ('103', 3, 28, 9, 48, 85)
        ]
        cursor.executemany("""
            INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, marks_data)
        
        # 5️⃣ INSERT ATTENDANCE 📅
        attendance_data = [
            ('101', 1, '2026-01-01', 'Present'),
            ('102', 2, '2026-01-01', 'Absent'),
            ('103', 3, '2026-01-01', 'Present')
        ]
        cursor.executemany("""
            INSERT INTO attendance (enrollment_no, subject_id, date, status)
            VALUES (%s, %s, %s, %s)
        """, attendance_data)
        
        conn.commit()
        print("✅ SUCCESS: SPDA Database Seeded with Perfectly Linked Test Data!")
        print("🔥 Charts and JOIN queries are now ready for verification.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    seed_database()
