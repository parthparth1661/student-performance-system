import mysql.connector
from db import get_db_connection
from werkzeug.security import generate_password_hash

def ensure_admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if admin table exists and has records
        print("Checking admin credentials...")
        cursor.execute("SELECT * FROM admin WHERE email = 'admin@spda.com'")
        admin = cursor.fetchone()
        
        if not admin:
            print("Admin not found. Creating default admin...")
            hashed_pw = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO admin (email, password) 
                VALUES (%s, %s)
            """, ('admin@spda.com', hashed_pw))
            conn.commit()
            print("Admin 'admin@spda.com' created with password 'admin123' (hashed).")
        else:
            print("Admin already exists.")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    ensure_admin()
