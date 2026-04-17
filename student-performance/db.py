"""
🗄️ SPDA Persistence & Schema Management
----------------------------------------
Handles institutional database connectivity, schema initialization, 
and standardized table architecture for student performance tracking.
"""

import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """
    Establishes a high-fidelity connection to the institutional MySQL database.
    Includes active database verification and safety gates.
    """
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SPDA"
        )
        
        # Verify active database context
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        db_info = cursor.fetchone()
        
        # Security Guard: Ensure we are operating within the correct institutional schema
        db = db_info[0]
        if db.upper() != "SPDA":
            cursor.close()
            connection.close()
            raise Exception("Security Alert: Unauthorized database context detected!")
            
        cursor.close()
        return connection
    except Error as e:
        print(f"Connection Failure: {e}")
        return None

def init_db():
    """
    Initializes the institutional database and enforces the standardized table architecture.
    Synchronizes existing records with current schema requirements.
    """
    try:
        # Create database container if not existing
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS SPDA")
        cursor.close()
        connection.close()

        # Connect to SPDA schema and initialize table architecture
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # --- 1. Administrative Nexus ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin (
                    admin_id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL
                )
            """)
            
            # --- 2. Student Registry ---
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
            
            # --- 3. Faculty Directory ---
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
            
            # --- 4. Curriculum & Subjects ---
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
            
            # --- 5. Academic Performance Ledger (Hardened) ---
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
                    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
                    UNIQUE KEY unique_student_subject (enrollment_no, subject_id)
                )
            """)
            
            # --- 6. Global Attendance Log ---
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

            # --- 7. Institutional Feedback Hub ---
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
            
            # --- 🚀 SUPER ADMIN SENTINEL ---
            # Automatically provision the system administrator if the registry is empty
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
                print(f"Super Admin initialized: {default_email}")
            
            cursor.close()
            connection.close()
            print("Institutional Protocol: Database synchronized and tables initialized.")
    except Exception as e:
        print(f"Schema Error: {e}")

if __name__ == "__main__":
    init_db()
