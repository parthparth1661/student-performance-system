from db import get_db_connection
conn = get_db_connection()
if conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT subject_id, subject_name FROM subjects LIMIT 10")
    for row in cursor.fetchall():
        print(row)
    conn.close()
