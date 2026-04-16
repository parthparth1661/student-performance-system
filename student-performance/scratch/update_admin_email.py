from db import get_db_connection

def set_admin_email():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE admin SET email = %s WHERE admin_id = 1", ("khevnamodi2@gmail.com",))
        conn.commit()
        print("Admin email updated successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    set_admin_email()
