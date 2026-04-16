import mysql.connector

def count_data():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        
        dbs = ["student_performance_db", "spda"]
        for db in dbs:
            print(f"Checking data in {db}:")
            cursor.execute(f"USE {db}")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            for table in tables:
                t_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
                count = cursor.fetchone()[0]
                print(f"- {t_name}: {count} rows")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    count_data()
