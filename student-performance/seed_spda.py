import mysql.connector
from db import get_db_connection

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Add Faculty
        print("Seeding Faculty...")
        cursor.execute("INSERT INTO faculty (faculty_name, email, department) VALUES (%s, %s, %s)", 
                       ("Dr. Alan Turing", "alan.turing@spda.edu", "BCA"))
        faculty_id = cursor.lastrowid
        
        # 2. Add Subject
        print("Seeding Subject...")
        cursor.execute("INSERT INTO subjects (subject_name, department, semester, faculty_id) VALUES (%s, %s, %s, %s)",
                       ("Database Management", "BCA", 3, faculty_id))
        subject_id = cursor.lastrowid
        
        # 3. Add Student
        print("Seeding Student...")
        from werkzeug.security import generate_password_hash
        pw = generate_password_hash("21BCA001@123")
        cursor.execute("INSERT INTO students (enrollment_no, name, email, department, semester, password_hash) VALUES (%s, %s, %s, %s, %s, %s)",
                       ("21BCA001", "Parth", "parth@spda.edu", "BCA", 3, pw))
        
        conn.commit()
        print("Seed data inserted successfully!")
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_data()
