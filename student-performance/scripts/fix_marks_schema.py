from db import get_db_connection

def fix_schema():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database.")
        return
    
    cursor = conn.cursor()
    try:
        # Check if 'status' column exists
        cursor.execute("SHOW COLUMNS FROM marks LIKE 'status'")
        if not cursor.fetchone():
            print("Adding 'status' column to 'marks' table...")
            cursor.execute("ALTER TABLE marks ADD COLUMN status VARCHAR(20)")
            conn.commit()
            print("'status' column added.")
        else:
            print("'status' column already exists.")
            
        # Also ensure other columns match the code expectations
        cols_to_add = {
            'total_marks': 'INT DEFAULT 100',
            'marks_obtained': 'INT'
        }
        
        for col, definition in cols_to_add.items():
            cursor.execute(f"SHOW COLUMNS FROM marks LIKE '{col}'")
            if not cursor.fetchone():
                print(f"Adding '{col}' column to 'marks' table...")
                cursor.execute(f"ALTER TABLE marks ADD COLUMN {col} {definition}")
                conn.commit()
                print(f"'{col}' column added.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fix_schema()
