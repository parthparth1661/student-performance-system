import mysql.connector

def check_schemas():
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='SPDA')
    cursor = conn.cursor()
    
    tables = ['students', 'subjects', 'faculty', 'marks', 'attendance']
    for table in tables:
        print(f"\n--- {table} ---")
        try:
            cursor.execute(f"DESCRIBE {table}")
            for row in cursor.fetchall():
                print(row)
        except Exception as e:
            print(f"Error: {e}")
            
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_schemas()
