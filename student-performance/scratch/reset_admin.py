from db import get_db_connection
from werkzeug.security import generate_password_hash

def reset_admin():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database.")
        return
    
    cursor = conn.cursor()
    email = "admin@spda.com"
    password = "Admin@123"
    hashed = generate_password_hash(password)
    
    try:
        # Delete existing admins to avoid confusion
        cursor.execute("DELETE FROM admin")
        
        # Insert fresh admin
        cursor.execute("INSERT INTO admin (email, password, name) VALUES (%s, %s, %s)", 
                       (email, hashed, "Super Admin"))
        conn.commit()
        print("-" * 30)
        print("✅ ADMIN CREDENTIALS RESET SUCCESSFUL")
        print("-" * 30)
        print(f"Email:    {email}")
        print(f"Password: {password}")
        print("-" * 30)
    except Exception as e:
        print(f"Error resetting admin: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    reset_admin()
