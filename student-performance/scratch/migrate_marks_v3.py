from db import get_db_connection

def migrate():
    conn = get_db_connection()
    if not conn:
        print("Database connection failed.")
        return
    
    try:
        cursor = conn.cursor()
        
        # 1. DROP old marks table
        print("Dropping old marks table...")
        cursor.execute("DROP TABLE IF EXISTS marks")
        
        # 2. Create new marks table according to requested schema
        print("Creating new marks table...")
        cursor.execute("""
        CREATE TABLE marks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            enrollment_no VARCHAR(50),
            subject_id INT,
            internal_marks INT DEFAULT 0,
            viva_marks INT DEFAULT 0,
            external_marks INT DEFAULT 0,
            total_marks INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate()
