import mysql.connector
from db import get_db_connection

def add_status_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        print("Alter sequence initiated...")
        cursor.execute("ALTER TABLE marks ADD status VARCHAR(20) DEFAULT 'PASS'")
        conn.commit()
        print("Column 'status' added successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_status_column()
