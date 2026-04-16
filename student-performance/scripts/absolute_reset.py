import mysql.connector

def absolute_reset():
    # 🎯 CONFIGURATION
    DB_NAME = "SPDA"
    SYSTEM_DBS = ["information_schema", "mysql", "performance_schema", "sys", "phpmyadmin", "test"]
    
    try:
        # Create connection without database
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        
        # 1. DELETE OTHER DATABASES (Cleanup 🔥)
        print("Cleaning up old databases...")
        cursor.execute("SHOW DATABASES")
        dbs = [db[0] for db in cursor.fetchall()]
        
        for db in dbs:
            if db != DB_NAME and db.lower() not in SYSTEM_DBS:
                print(f"Dropping database: {db}...")
                cursor.execute(f"DROP DATABASE IF EXISTS {db}")
        
        # 2. RECREATE SPDA
        print(f"Recreating {DB_NAME}...")
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")
        
        # 3. CREATE TABLES WITH PROPER SCHEMA 🎯
        
        # Admin Table
        print("Creating table: admin...")
        cursor.execute("""
            CREATE TABLE admin (
                admin_id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        """)
        
        # Faculty Table
        print("Creating table: faculty...")
        cursor.execute("""
            CREATE TABLE faculty (
                faculty_id INT AUTO_INCREMENT PRIMARY KEY,
                faculty_name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                department VARCHAR(50)
            )
        """)
        
        # Students Table
        print("Creating table: students...")
        cursor.execute("""
            CREATE TABLE students (
                enrollment_no VARCHAR(20) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                department VARCHAR(50),
                semester INT,
                password_hash VARCHAR(255),
                is_password_changed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Subjects Table
        print("Creating table: subjects...")
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
        
        # Marks Table
        print("Creating table: marks...")
        cursor.execute("""
            CREATE TABLE marks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment_no VARCHAR(20),
                subject_id INT,
                internal_marks INT DEFAULT 0,
                viva_marks INT DEFAULT 0,
                external_marks INT DEFAULT 0,
                total_marks INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
            )
        """)
        
        # Attendance Table
        print("Creating table: attendance...")
        cursor.execute("""
            CREATE TABLE attendance (
                attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment_no VARCHAR(20),
                subject_id INT,
                date DATE,
                status VARCHAR(20),
                FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        print("\n✅ SUCCESS: SPDA database created with clean standardized schema!")
        print("🔥 System is now strictly isolated to SPDA Only.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    absolute_reset()
