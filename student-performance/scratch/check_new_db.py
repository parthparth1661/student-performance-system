import mysql.connector

def check_new_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="SPDA"
        )
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"Tables in SPDA:")
        for table in tables:
            print(f"- {table[0]}")
            
            cursor.execute(f"DESCRIBE {table[0]}")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  {col[0]} ({col[1]})")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_new_db()
