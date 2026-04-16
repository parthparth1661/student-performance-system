from db import get_db_connection

def sync_db():
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        # Check columns
        cursor.execute("DESCRIBE marks")
        columns = [col[0] for col in cursor.fetchall()]
        
        if 'status' not in columns:
            print("Adding status column...")
            cursor.execute("ALTER TABLE marks ADD COLUMN status VARCHAR(20)")
            
        if 'marks_obtained' not in columns:
            print("Adding marks_obtained column...")
            cursor.execute("ALTER TABLE marks ADD COLUMN marks_obtained INT")
            
        if 'total_marks' not in columns:
            print("Adding total_marks column...")
            cursor.execute("ALTER TABLE marks ADD COLUMN total_marks INT DEFAULT 100")
            
        # Update null status values
        print("Updating status for existing records...")
        cursor.execute("""
            UPDATE marks 
            SET status = CASE 
                WHEN (marks_obtained / total_marks) * 100 >= 40 THEN 'PASS' 
                ELSE 'FAIL' 
            END 
            WHERE status IS NULL
        """)
        
        conn.commit()
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    sync_db()
