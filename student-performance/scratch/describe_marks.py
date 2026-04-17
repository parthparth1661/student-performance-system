
import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="spda"
    )
    cursor = conn.cursor()
    cursor.execute("DESCRIBE marks")
    for col in cursor:
        print(col)
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
