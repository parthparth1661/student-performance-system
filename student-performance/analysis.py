import pandas as pd
import os
from db import get_db_connection

# Ensure vital directories exist for charts and exports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: CHARTS_DIR is kept only for legacy compatibility if external modules expect it, 
# although Dashboard now uses Chart.js
CHARTS_DIR = os.path.join(BASE_DIR, 'static', 'charts')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')

for directory in [CHARTS_DIR, UPLOADS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

def build_dashboard_conditions(filters={}):
    """Centralized high-precision filter builder for all analytical modules"""
    conditions = []
    values = []
    
    department = filters.get('department')
    semester = filters.get('semester')
    subject = filters.get('subject')
    search = filters.get('search')
    attendance_filter = filters.get('attendance')
    subject_id = filters.get('subject_id')

    if department:
        conditions.append("s.department = %s")
        values.append(department)

    if semester:
        conditions.append("s.semester = %s")
        values.append(semester)

    if subject:
        conditions.append("LOWER(sub.subject_name) = LOWER(%s)")
        values.append(subject)

    if subject_id:
        conditions.append("sub.subject_id = %s")
        values.append(subject_id)

    if search:
        conditions.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
        values.append(f"%{search}%")
        values.append(f"%{search}%")

    if attendance_filter == "low":
        conditions.append("""
        s.enrollment_no IN (
            SELECT enrollment_no 
            FROM attendance 
            GROUP BY enrollment_no 
            HAVING COALESCE(COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0), 0) < 75
        )
        """)
    elif attendance_filter == "high":
        conditions.append("""
        s.enrollment_no IN (
            SELECT enrollment_no 
            FROM attendance 
            GROUP BY enrollment_no 
            HAVING COALESCE(COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0), 0) >= 75
        )
        """)
    
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, values

def get_dashboard_stats(filters={}):
    conn = get_db_connection()
    if not conn:
        return {'total_students': 0, 'total_subjects': 0, 'avg_marks': 0, 'attendance_percentage': 0, 'low_attendance_count': 0, 'top_performer': 'N/A'}
    
    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)

        # 🥇 TOTAL STUDENTS (Join-Aware)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT s.enrollment_no) as count 
            FROM students s
            LEFT JOIN marks m ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """, values)
        total_students = cursor.fetchone()['count'] or 0
        
        # 🥈 TOTAL SUBJECTS
        department = filters.get('department')
        if department:
            cursor.execute("SELECT COUNT(*) as count FROM subjects WHERE department = %s", (department,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM subjects")
        total_subjects = cursor.fetchone()['count'] or 0
        
        # 🥉 AVERAGE MARKS
        avg_query = f"""
            SELECT AVG(m.total_marks) AS avg_marks 
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(avg_query, values)
        avg_marks = round(cursor.fetchone()['avg_marks'] or 0, 2)
        
        # 🏆 ATTENDANCE %
        attn_query = f"""
            SELECT COALESCE(COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0) 
            AS attendance_percentage 
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            LEFT JOIN subjects sub ON a.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(attn_query, values)
        attendance_percentage = round(cursor.fetchone()['attendance_percentage'] or 0, 2)

        # 💡 TOP PERFORMER
        top_query = f"""
            SELECT s.name, AVG(m.total_marks) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY s.enrollment_no, s.name
            ORDER BY avg_marks DESC
            LIMIT 1
        """
        cursor.execute(top_query, values)
        top_data = cursor.fetchone()
        top_performer = top_data['name'] if top_data else "N/A"

        # ⚠️ AT RISK COUNT
        risk_filters = filters.copy()
        risk_filters.pop('attendance', None)
        risk_where, risk_values = build_dashboard_conditions(risk_filters)
        risk_base = risk_where if risk_where else " WHERE 1=1 "
        
        cursor.execute(f"""
            SELECT COUNT(DISTINCT s.enrollment_no) as count
            FROM students s
            LEFT JOIN marks m ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects sub ON m.subject_id = sub.subject_id
            {risk_base}
            AND s.enrollment_no IN (
                SELECT enrollment_no FROM attendance 
                GROUP BY enrollment_no 
                HAVING COALESCE(COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0), 0) < 75
            )
        """, risk_values)
        low_attendance_count = cursor.fetchone()['count'] or 0
        
        cursor.close()
        conn.close()
        return {
            'total_students': total_students, 'total_subjects': total_subjects,
            'avg_marks': avg_marks, 'attendance_percentage': attendance_percentage,
            'low_attendance_count': low_attendance_count, 'top_performer': top_performer
        }
    except Exception as e:
        print(f"Error in analytics: {e}")
        return {'total_students': 0, 'total_subjects': 0, 'avg_marks': 0, 'attendance_percentage': 0, 'low_attendance_count': 0, 'top_performer': "N/A"}

def get_performance_overview(filters={}, limit=10, offset=0):
    """Student ledger logic for paginated views"""
    conn = get_db_connection()
    if not conn: return [], 0
    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        query = f"""
            SELECT 
                s.enrollment_no, s.name, s.department, s.semester,
                sub.subject_name, AVG(m.total_marks) AS marks_obtained,
                COALESCE(COUNT(CASE WHEN a.status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0), 0) AS attendance_percentage
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no AND sub.subject_id = a.subject_id
            {where_clause}
            GROUP BY s.enrollment_no, sub.subject_id
            ORDER BY s.enrollment_no ASC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, values + [limit, offset])
        data = cursor.fetchall()
        
        count_query = f"""
            SELECT COUNT(*) as total FROM (
                SELECT s.enrollment_no, sub.subject_id FROM students s
                JOIN marks m ON s.enrollment_no = m.enrollment_no
                JOIN subjects sub ON m.subject_id = sub.subject_id
                {where_clause}
                GROUP BY s.enrollment_no, sub.subject_id
            ) as sq
        """
        cursor.execute(count_query, values)
        total_records = cursor.fetchone()['total'] or 0
        
        cursor.close()
        conn.close()
        return data, total_records
    except Exception as e:
        print(f"Ledger error: {e}")
        return [], 0

def get_dashboard_chart_data(filters={}):
    """Returns high-density analytical JSON payloads for Chart.js"""
    conn = get_db_connection()
    if not conn: return {}

    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        analytics = {
            'subject_avg': {'labels': [], 'values': []},
            'results_dist': {'labels': ['Pass', 'Fail'], 'values': [0, 0]},
            'attendance_dist': {'labels': ['Present', 'Absent'], 'values': [0, 0]},
            'performance_trend': {'labels': [], 'values': []}
        }

        # 1. Subject-wise average
        query = f"""
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN students s ON s.enrollment_no = m.enrollment_no
            {where_clause}
            GROUP BY sub.subject_name
            ORDER BY sub.subject_name ASC
        """
        cursor.execute(query, values)
        data = cursor.fetchall()
        analytics['subject_avg']['labels'] = [r['subject_name'] for r in data]
        analytics['subject_avg']['values'] = [float(r['avg_marks']) for r in data]

        # 2. Results distribution
        query = f"""
            SELECT 
                SUM(CASE WHEN m.total_marks >= 40 THEN 1 ELSE 0 END) as pass_count,
                SUM(CASE WHEN m.total_marks < 40 THEN 1 ELSE 0 END) as fail_count
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(query, values)
        data = cursor.fetchone()
        if data:
            analytics['results_dist']['values'] = [int(data['pass_count'] or 0), int(data['fail_count'] or 0)]

        # 3. Attendance distribution
        query = f"""
            SELECT 
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            LEFT JOIN subjects sub ON a.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(query, values)
        data = cursor.fetchone()
        if data:
            analytics['attendance_dist']['values'] = [int(data['present'] or 0), int(data['absent'] or 0)]

        # 4. Performance Trend (Exam Components)
        query = f"""
            SELECT 
                AVG(m.internal_marks) as Internal,
                AVG(m.viva_marks) as Viva,
                AVG(m.external_marks) as External
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(query, values)
        data = cursor.fetchone()
        if data:
            analytics['performance_trend']['labels'] = ['Unit Tests', 'Mid Term', 'Semester Final']
            analytics['performance_trend']['values'] = [
                float(data['Internal'] or 0),
                float(data['Viva'] or 0),
                float(data['External'] or 0)
            ]

        cursor.close()
        conn.close()
        return analytics
    except Exception as e:
        print(f"Chart Analytics Error: {e}")
        return {}

def process_csv(file_path):
    """Consolidated CSV processing logic for bulk uploads"""
    try:
        df = pd.read_csv(file_path)
        cols = [c.strip().lower() for c in df.columns]
        df.columns = cols 
        if 'roll_no' in cols and 'enrollment_no' not in cols:
            df.rename(columns={'roll_no': 'enrollment_no'}, inplace=True)
            cols = list(df.columns)
        
        conn = get_db_connection()
        if not conn: return False, "DB Connection Failed"
        
        cursor = conn.cursor()
        success_count = 0
        
        # Determine CSV Type by columns
        if all(x in cols for x in ['enrollment_no', 'name', 'email', 'department', 'semester']):
            from werkzeug.security import generate_password_hash
            for _, row in df.iterrows():
                pw_hash = generate_password_hash(str(row['enrollment_no']))
                cursor.execute("""
                    INSERT INTO students (enrollment_no, name, email, department, semester, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email)
                """, (row['enrollment_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
                success_count += 1
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'date', 'status']):
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO attendance (enrollment_no, subject_id, date, status)
                    VALUES (%s, %s, %s, %s)
                """, (row['enrollment_no'], row['subject_id'], row['date'], row['status']))
                success_count += 1
        else:
            return False, "Unrecognized Header Format"

        conn.commit()
        conn.close()
        return True, f"Successfully processed {success_count} records."
    except Exception as e:
        return False, str(e)

# --- Student Profile Helpers ---
def get_student_details(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
    student = cursor.fetchone()
    conn.close()
    return student

def get_student_marks(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.*, sub.subject_name as subject
        FROM marks m JOIN subjects sub ON m.subject_id = sub.subject_id 
        WHERE m.enrollment_no = %s
    """, (enrollment_no,))
    marks = cursor.fetchall()
    conn.close()
    return [{'subject': r['subject'], 'internal_marks': r['internal_marks'], 
             'viva_marks': r['viva_marks'], 'external_marks': r['external_marks'], 
             'total': r['total_marks']} for r in marks]

def calculate_student_summary(enrollment_no):
    marks = get_student_marks(enrollment_no)
    if not marks: return {'total_subjects': 0, 'avg_marks': 0}
    total_m = sum(m['total'] for m in marks)
    return {
        'total_subjects': len(marks),
        'avg_marks': round(total_m / len(marks), 2) if marks else 0
    }
