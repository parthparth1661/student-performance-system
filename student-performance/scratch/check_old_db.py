import mysql.connector

def check_old_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        
        old_db = "student_performance_db"
        cursor.execute(f"SHOW DATABASES LIKE '{old_db}'")
        if not cursor.fetchone():
            print(f"Database {old_db} not found.")
            return

        cursor.execute(f"USE {old_db}")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Tables in {old_db}:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Show columns for each table to help with migration
            cursor.execute(f"DESCRIBE {table[0]}")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  {col[0]} ({col[1]})")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_old_db()
