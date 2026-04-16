from db import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("DESCRIBE students")
for row in cursor.fetchall():
    print(row)
conn.close()
