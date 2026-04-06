import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        # 🎯 STRICT CONFIGURATION: SPDA Only
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='SPDA'
        )
        
        # 🔥 SAFETY CHECK: Validation
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()[0]
        cursor.close()
        
        if db_name.upper() != "SPDA":
            connection.close()
            raise Exception(f"CRITICAL ERROR: Connected to unauthorized database '{db_name}'! Connection terminated.")
            
        return connection
    except Error as e:
        print(f"Error connecting to SPDA MySQL: {e}")
        return None

def init_db():
    try:
        # Connect to create database if not exists
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS SPDA")
        cursor.close()
        connection.close()

        # Connect to SPDA and create standardized tables
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # 1. Admin Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin (
                    admin_id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)
            
            # 2. Students Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    enrollment_no VARCHAR(20) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    department VARCHAR(50),
                    semester INT,
                    password_hash VARCHAR(255),
                    is_password_changed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # 3. Faculty Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faculty (
                    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
                    faculty_name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    department VARCHAR(50)
                )
            """)
            
            # 4. Subjects Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    subject_id INT AUTO_INCREMENT PRIMARY KEY,
                    subject_name VARCHAR(100) NOT NULL,
                    department VARCHAR(50),
                    semester INT,
                    faculty_id INT,
                    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
                )
            """)
            
            # 5. Marks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marks (
                    marks_id INT AUTO_INCREMENT PRIMARY KEY,
                    enrollment_no VARCHAR(20),
                    subject_id INT,
                    exam_type VARCHAR(50),
                    marks_obtained INT,
                    total_marks INT DEFAULT 100,
                    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
                )
            """)
            
            # 6. Attendance Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                    enrollment_no VARCHAR(20),
                    subject_id INT,
                    date DATE,
                    status VARCHAR(20),
                    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
                )
            """)
            
            connection.commit()
            cursor.close()
            connection.close()
            print("SPDA Database and standardized tables initialized.")
    except Exception as e:
        print(f"Error initializing SPDA database: {e}")

if __name__ == "__main__":
    init_db()
