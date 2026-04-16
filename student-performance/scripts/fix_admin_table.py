from db import get_db_connection
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if name column exists
    cursor.execute("SHOW COLUMNS FROM admin LIKE 'name'")
    if not cursor.fetchone():
        print("Column 'name' missing. Adding it...")
        cursor.execute("ALTER TABLE admin ADD COLUMN name VARCHAR(100)")
        conn.commit()
        print("Column 'name' added successfully.")
    else:
        print("Column 'name' already exists.")
    
    # Verify
    cursor.execute("DESCRIBE admin")
    for row in cursor.fetchall():
        print(row)
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
