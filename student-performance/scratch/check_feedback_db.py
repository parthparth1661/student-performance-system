import mysql.connector

try:
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="SPDA")
    cursor = conn.cursor()
    cursor.execute("DESCRIBE feedback")
    columns = [row[0] for row in cursor.fetchall()]
    print(f"Columns: {columns}")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
