from db import get_db_connection
from werkzeug.security import generate_password_hash

def ensure_admin():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect.")
        return
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if admin exists
        cursor.execute("SELECT * FROM admin WHERE email = %s", ("admin@spda.com",))
        admin = cursor.fetchone()
        
        if admin:
            print("Admin already exists. Updating password...")
            hashed_pw = generate_password_hash("admin123")
            cursor.execute("UPDATE admin SET password = %s WHERE email = %s", (hashed_pw, "admin@spda.com"))
        else:
            print("Creating default admin account...")
            hashed_pw = generate_password_hash("admin123")
            cursor.execute("INSERT INTO admin (email, password) VALUES (%s, %s)", ("admin@spda.com", hashed_pw))
            
        conn.commit()
        print("-" * 30)
        print("✅ ADMIN CREDENTIALS FINALIZED")
        print("-" * 30)
        print("Email:    admin@spda.com")
        print("Password: admin123")
        print("-" * 30)
        
    except Exception as e:
        print(f"Error initializing admin: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    ensure_admin()
