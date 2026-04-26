from db import get_db_connection

def list_admins():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM admin")
        admins = cursor.fetchall()
        
        if not admins:
            print("No admin users found in the database.")
        else:
            print(f"Found {len(admins)} admin(s):")
            for admin in admins:
                print("-" * 30)
                print(f"ID:       {admin.get('admin_id')}")
                print(f"Email:    {admin.get('email')}")
                # We can't show the password since it's hashed, but we can verify it
                print(f"Password: (Hashed in database)")
                print("-" * 30)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    list_admins()
