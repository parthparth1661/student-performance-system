import mysql.connector

try:
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="SPDA")
    cursor = conn.cursor()
    cursor.execute("DESCRIBE feedback")
    columns = [row[0] for row in cursor.fetchall()]
    
    updates = []
    if "rating" not in columns:
        updates.append("ADD COLUMN rating INT DEFAULT 5")
    if "faculty_name" not in columns:
        updates.append("ADD COLUMN faculty_name VARCHAR(100)")
    if "department" not in columns:
        updates.append("ADD COLUMN department VARCHAR(50)")
        
    if updates:
        query = f"ALTER TABLE feedback {', '.join(updates)}"
        print(f"Executing: {query}")
        cursor.execute(query)
        conn.commit()
        print("Schema updated successfully.")
    else:
        print("Schema already up to date.")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
