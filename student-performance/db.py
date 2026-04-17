import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        # 1️⃣ Check Database Connection 🎯
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SPDA"
        )
        
        # 2️⃣ Verify Active Database 🕵️‍♂️
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        db_info = cursor.fetchone()
        
        # 4️⃣ Add Safety Check (IMPORTANT 🔥)
        db = db_info[0]
        if db.upper() != "SPDA":
            cursor.close()
            connection.close()
            raise Exception("Wrong database connected!")
            
        cursor.close()
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
                    name VARCHAR(100),
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
                    is_password_changed BOOLEAN DEFAULT FALSE,
                    profile_pic VARCHAR(255) DEFAULT 'default.png'
                )
            """)
            
            # 3. Faculty Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faculty (
                    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
                    faculty_name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    department VARCHAR(50),
                    contact_no VARCHAR(15),
                    password_hash VARCHAR(255)
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
            
            # 5. Marks Table (Redesigned 🚀)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    enrollment_no VARCHAR(20),
                    subject_id INT,
                    internal_marks INT DEFAULT 0,
                    viva_marks INT DEFAULT 0,
                    external_marks INT DEFAULT 0,
                    total_marks INT DEFAULT 0,
                    result VARCHAR(10) DEFAULT 'Fail',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

            # 7. Feedback Table (Updated for Rating & Professional Mapping)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id VARCHAR(50),
                    student_name VARCHAR(100),
                    department VARCHAR(50),
                    semester INT,
                    subject VARCHAR(255),
                    faculty VARCHAR(100),
                    rating INT DEFAULT 5,
                    comment TEXT,
                    admin_reply TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            connection.commit()
            
            # 🚀 START: SUPER ADMIN SENTINEL
            cursor.execute("SELECT COUNT(*) as count FROM admin")
            if cursor.fetchone()[0] == 0:
                from werkzeug.security import generate_password_hash
                default_email = 'admin@spda.com'
                default_pass = 'Admin@123'
                hashed_pass = generate_password_hash(default_pass)
                
                cursor.execute("""
                    INSERT INTO admin (email, password) 
                    VALUES (%s, %s)
                """, (default_email, hashed_pass))
                connection.commit()
                print(f"✨ Super Admin initialized: {default_email} / {default_pass}")
            
            cursor.close()
            connection.close()
            print("SPDA Database and merged standardized tables initialized.")
    except Exception as e:
        print(f"Error initializing SPDA database: {e}")

if __name__ == "__main__":
    init_db()
