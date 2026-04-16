import mysql.connector
try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="SPDA"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT DATABASE()")
    db = cursor.fetchone()
    print(f"Database Verification: {db}")
    
    if db[0] != "SPDA":
        raise Exception("Wrong database connected!")
    else:
        print("✅ SUCCESS: Strictly connected to SPDA.")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ ERROR: {e}")
