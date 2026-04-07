from werkzeug.security import generate_password_hash
from db import get_db_connection, init_db
import mysql.connector

def create_super_admin():
    # Ensure tables and initial admin are set up
    init_db()
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return

    cursor = conn.cursor()
    # 🎯 Standardize on Email-based Login
    email = 'admin@spda.com'
    password = 'Admin@123'
    password_hash = generate_password_hash(password)

    try:
        cursor.execute("SELECT COUNT(*) FROM admin WHERE email = %s", (email,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO admin (email, password) VALUES (%s, %s)", 
                           (email, password_hash))
            conn.commit()
            print(f"✨ Super Admin created successfully!")
            print(f"📧 Email: {email}")
            print(f"🔑 Password: {password}")
        else:
            print(f"ℹ️ Admin '{email}' already exists.")
    except mysql.connector.Error as err:
        print(f"❌ Error creating admin: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_super_admin()
