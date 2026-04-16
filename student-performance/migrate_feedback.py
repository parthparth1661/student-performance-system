from db import get_db_connection

def add_rating_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE feedback ADD COLUMN rating INT DEFAULT 5")
        conn.commit()
        print("Successfully added 'rating' column to feedback table.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_rating_column()
