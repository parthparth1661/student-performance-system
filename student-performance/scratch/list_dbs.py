import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=""
    )
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES")
    databases = cursor.fetchall()
    print("Databases found:")
    for db in databases:
        print(f"- {db[0]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
