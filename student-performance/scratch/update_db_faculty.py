import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="SPDA"
    )
    cursor = conn.cursor()
    cursor.execute("DESCRIBE faculty")
    columns = [row[0] for row in cursor.fetchall()]
    print(f"Columns: {columns}")
    
    if "contact_no" not in columns:
        print("Adding contact_no column...")
        cursor.execute("ALTER TABLE faculty ADD COLUMN contact_no VARCHAR(15)")
        conn.commit()
        print("Column added successfully.")
    else:
        print("Column already exists.")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
