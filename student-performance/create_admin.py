from werkzeug.security import generate_password_hash
from db import get_db_connection, init_db
import mysql.connector

def create_super_admin():
    # Ensure tables exist
    init_db()
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return

    cursor = conn.cursor()
    username = 'admin'
    password = 'Admin@123'
    password_hash = generate_password_hash(password)

    try:
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)", 
                       (username, password_hash))
        conn.commit()
        print(f"Super Admin created successfully!")
        print(f"Username: {username}")
        print(f"Password: {password}")
    except mysql.connector.Error as err:
        if err.errno == 1062: # Duplicate entry
            print(f"Admin '{username}' already exists.")
        else:
            print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_super_admin()
