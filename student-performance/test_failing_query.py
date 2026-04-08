from db import get_db_connection

def test_query():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT m.*, s.name as student_name, sub.subject_name, sub.department, sub.semester
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            WHERE 1=1
        """
        stats_query = f"""
            SELECT 
                COUNT(*) as total_entries,
                AVG(marks_obtained) as avg_marks,
                MAX(marks_obtained) as top_score,
                SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as pass_count
            FROM ({query}) as filtered_marks
        """
        cursor.execute(stats_query)
        print("Stats Result:", cursor.fetchone())
    except Exception as e:
        print(f"Query Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    test_query()
