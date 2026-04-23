from db import get_db_connection
from werkzeug.security import check_password_hash

def check_current_admin():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to database.")
        return
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email, password FROM admin")
    admins = cursor.fetchall()
    
    if not admins:
        print("No admin users found in the database.")
    else:
        print(f"Found {len(admins)} admin(s):")
        for admin in admins:
            email = admin['email']
            hashed = admin['password']
            
            p1 = "admin123"
            p2 = "Admin@123"
            
            works1 = check_password_hash(hashed, p1)
            works2 = check_password_hash(hashed, p2)
            
            if works1:
                print(f"Email: {email} | Valid Password: {p1}")
            elif works2:
                print(f"Email: {email} | Valid Password: {p2}")
            else:
                print(f"Email: {email} | Password: Unknown (Hash: {hashed[:10]}...)")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_current_admin()
