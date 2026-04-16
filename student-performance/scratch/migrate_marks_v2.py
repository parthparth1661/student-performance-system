import mysql.connector
from db import DB_CONFIG

def migrate():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # DROP old marks table
        print("Dropping old marks table...")
        cursor.execute("DROP TABLE IF EXISTS marks")
        
        # Create new marks table
        print("Creating new marks table...")
        cursor.execute("""
        CREATE TABLE marks (
            marks_id INT AUTO_INCREMENT PRIMARY KEY,
            enrollment_no VARCHAR(50),
            subject_id INT,
            internal_marks INT DEFAULT 0,
            viva_marks INT DEFAULT 0,
            external_marks INT DEFAULT 0,
            total_marks INT DEFAULT 0,
            marks_obtained INT DEFAULT 0,
            exam_type VARCHAR(50) DEFAULT 'Final',
            status VARCHAR(20) DEFAULT 'PASS',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    migrate()
