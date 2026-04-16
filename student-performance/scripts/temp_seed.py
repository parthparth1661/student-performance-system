import mysql.connector
from db import get_db_connection
from werkzeug.security import generate_password_hash

def seed():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Faculty
        print("Seeding Faculty...")
        cursor.execute("INSERT INTO faculty (faculty_name, email, department) VALUES (%s, %s, %s)", 
                       ("Dr. Alan Turing", "alan.turing@spda.edu", "BCA"))
        faculty_id = cursor.lastrowid
        
        # Student
        print("Seeding Student...")
        pw = generate_password_hash("21BCA001@123")
        cursor.execute("INSERT INTO students (enrollment_no, name, email, department, semester, password_hash) VALUES (%s, %s, %s, %s, %s, %s)",
                       ("21BCA001", "Parth", "parth@spda.edu", "BCA", 3, pw))
        
        # Subject
        print("Seeding Subject...")
        cursor.execute("INSERT INTO subjects (subject_name, department, semester, faculty_id) VALUES (%s, %s, %s, %s)",
                       ("Database Management", "BCA", 3, faculty_id))
        subject_id = cursor.lastrowid
        
        # Marks
        print("Seeding Marks...")
        cursor.execute("INSERT INTO marks (enrollment_no, subject_id, exam_type, marks_obtained, total_marks) VALUES (%s, %s, %s, %s, %s)",
                       ("21BCA001", subject_id, "Internal", 85, 100))
        cursor.execute("INSERT INTO marks (enrollment_no, subject_id, exam_type, marks_obtained, total_marks) VALUES (%s, %s, %s, %s, %s)",
                       ("21BCA001", subject_id, "External", 70, 100))
        
        # Attendance
        print("Seeding Attendance...")
        from datetime import date
        cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)",
                       ("21BCA001", subject_id, date.today(), "Present"))
        
        conn.commit()
        print("SPDA data seeded successfully!")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed()
