import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',  # Default XAMPP password is empty
            database='student_performance_db'
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    try:
        # Connect without database to create it if it doesn't exist
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS student_performance_db")
        cursor.close()
        connection.close()

        # Connect to the database to create tables
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # Create students table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id INT AUTO_INCREMENT PRIMARY KEY,
                    roll_no VARCHAR(20) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) UNIQUE NOT NULL,
                    department VARCHAR(50),
                    semester INT
                )
            """)
            
            # Create marks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marks (
                    marks_id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    subject VARCHAR(50) NOT NULL,
                    marks INT NOT NULL,
                    exam_type VARCHAR(20),
                    exam_date DATE,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)
            
            # Create attendance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT NOT NULL,
                    attendance_date DATE NOT NULL,
                    status VARCHAR(10) NOT NULL,
                    remarks VARCHAR(200),
                    UNIQUE(student_id, attendance_date),
                    FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
                )
            """)

            # Create admins table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    admin_id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            connection.commit()
            cursor.close()
            connection.close()
            print("Database initialized successfully.")
    except Error as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
