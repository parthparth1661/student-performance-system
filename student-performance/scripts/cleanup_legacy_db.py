import mysql.connector

def cleanup_legacy_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        
        # Target legacy databases
        legacy_dbs = ["student_performance", "student_performance_db"]
        
        for db in legacy_dbs:
            cursor.execute(f"SHOW DATABASES LIKE '{db}'")
            if cursor.fetchone():
                print(f"Dropping legacy database: {db}...")
                cursor.execute(f"DROP DATABASE {db}")
                print(f"SUCCESS: {db} removed.")
            else:
                print(f"INFO: {db} does not exist.")
                
        # Verify current DB
        cursor.execute("SHOW DATABASES LIKE 'spda'")
        if cursor.fetchone():
            print("VERIFIED: 'spda' exists.")
        else:
            print("WARNING: 'spda' not found!")
            
        conn.close()
    except Exception as e:
        print(f"ERROR during cleanup: {e}")

if __name__ == "__main__":
    cleanup_legacy_db()
