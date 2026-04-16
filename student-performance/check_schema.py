from db import get_db_connection

def check_feedback_schema():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("DESCRIBE feedback")
        columns = cursor.fetchall()
        print("COLUMNS IN FEEDBACK TABLE:")
        for col in columns:
            print(f" - {col['Field']} ({col['Type']})")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_feedback_schema()
