from db import get_db_connection

def verify_joins():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Performance Join Query 🎯
        query = """
            SELECT 
                s.name as student_name,
                sub.subject_name,
                m.marks_obtained,
                m.exam_type,
                a.status as attendance_status,
                a.date as attendance_date
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN attendance a 
                ON s.enrollment_no = a.enrollment_no 
                AND sub.subject_id = a.subject_id
        """
        
        print("--- RUNNING INTEGRATED JOIN QUERY ---")
        cursor.execute(query)
        results = cursor.fetchall()
        
        if results:
            print(f"✅ Found {len(results)} connected records:")
            print("-" * 80)
            print(f"{'Student':<15} | {'Subject':<20} | {'Marks':<5} | {'Exam':<10} | {'Status':<10}")
            print("-" * 80)
            for row in results:
                print(f"{row['student_name']:<15} | {row['subject_name']:<20} | {row['marks_obtained']:<5} | {row['exam_type']:<10} | {row['attendance_status']:<10}")
            print("-" * 80)
        else:
            print("❌ No joined data found. Checking individual tables...")
            check_tables(cursor)

    except Exception as e:
        print(f"Error executing JOIN: {e}")
    finally:
        cursor.close()
        conn.close()

def check_tables(cursor):
    tables = ['students', 'subjects', 'marks', 'attendance']
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = cursor.fetchone()['count']
        print(f"Table '{table}': {count} records found.")
        
        if count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            sample = cursor.fetchone()
            print(f"   Sample from {table}: {sample}")

if __name__ == "__main__":
    verify_joins()
