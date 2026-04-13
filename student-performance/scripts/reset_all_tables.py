import mysql.connector

def update_tables():
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='SPDA')
    cursor = conn.cursor()
    
    try:
        # 1. Students: enrollment_no, name, email, department, semester
        print("Updating students table...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("DROP TABLE IF EXISTS students_old")
        cursor.execute("RENAME TABLE students TO students_old")
        cursor.execute("""
            CREATE TABLE students (
                enrollment_no VARCHAR(20) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150),
                department VARCHAR(50),
                semester INT,
                password_hash VARCHAR(255),
                is_password_changed BOOLEAN DEFAULT FALSE
            )
        """)
        # Migrating data if exists
        try:
            cursor.execute("INSERT INTO students (enrollment_no, name, email, department, semester) SELECT roll_no, name, email, department, semester FROM students_old")
        except:
            pass
            
        # 2. Faculty: faculty_name, email, department
        print("Updating faculty table...")
        cursor.execute("DROP TABLE IF EXISTS faculty")
        cursor.execute("""
            CREATE TABLE faculty (
                faculty_id INT AUTO_INCREMENT PRIMARY KEY,
                faculty_name VARCHAR(100) NOT NULL,
                email VARCHAR(150),
                department VARCHAR(50)
            )
        """)
        
        # 3. Subjects: subject_name, department, semester, faculty_id
        print("Updating subjects table...")
        cursor.execute("DROP TABLE IF EXISTS subjects")
        cursor.execute("""
            CREATE TABLE subjects (
                subject_id INT AUTO_INCREMENT PRIMARY KEY,
                subject_name VARCHAR(100) NOT NULL,
                department VARCHAR(50),
                semester INT,
                faculty_id INT,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
            )
        """)
        
        # 4. Marks: enrollment_no, subject_id, exam_type, marks_obtained, total_marks
        print("Updating marks table...")
        cursor.execute("DROP TABLE IF EXISTS marks")
        cursor.execute("""
            CREATE TABLE marks (
                marks_id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment_no VARCHAR(20),
                subject_id INT,
                exam_type VARCHAR(20),
                marks_obtained INT,
                total_marks INT DEFAULT 100,
                FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
            )
        """)
        
        # 5. Attendance: enrollment_no, subject_id, date, status
        print("Updating attendance table...")
        cursor.execute("DROP TABLE IF EXISTS attendance")
        cursor.execute("""
            CREATE TABLE attendance (
                attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment_no VARCHAR(20),
                subject_id INT,
                date DATE,
                status VARCHAR(10),
                FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        print("All tables updated to match requirements!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_tables()
