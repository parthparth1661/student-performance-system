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
                # Extract contact_no with flexible support for common variations
                contact = str(row.get('contact_no') or row.get('phone') or row.get('contact') or '').strip()
                
                pw_hash = generate_password_hash(str(row['enrollment_no']))
                cursor.execute("""
                    INSERT INTO students (enrollment_no, name, email, department, semester, contact_no, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        name=VALUES(name), 
                        email=VALUES(email),
                        contact_no=VALUES(contact_no)
                """, (row['enrollment_no'], row['name'], row['email'], row['department'], row['semester'], contact, pw_hash))
                success_count += 1
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'date', 'status']):
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO attendance (enrollment_no, subject_id, date, status)
                    VALUES (%s, %s, %s, %s)
                """, (row['enrollment_no'], row['subject_id'], row['date'], row['status']))
                success_count += 1
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'internal', 'viva', 'external']):
            for _, row in df.iterrows():
                i, v, e = int(row['internal']), int(row['viva']), int(row['external'])
                total = i + v + e
                cursor.execute("""
                    INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE internal_marks=VALUES(internal_marks), viva_marks=VALUES(viva_marks), 
                                         external_marks=VALUES(external_marks), total_marks=VALUES(total_marks)
                """, (row['enrollment_no'], row['subject_id'], i, v, e, total))
                success_count += 1
        else:
            return False, "Unrecognized Header Format"

        conn.commit()
        conn.close()
        return True, f"Successfully processed {success_count} records."
    except Exception as e:
        return False, str(e)

def export_admin_excel(dept, sem, sub, search, att):
    """Exports administrative ledger to Excel with active filters"""
    filters = {
        'department': dept if dept != 'All' else None,
        'semester': sem if sem != 'All' else None,
        'subject': sub if sub != 'All' else None,
        'search': search,
        'attendance': att
    }
    data, _ = get_performance_overview(filters, limit=10000)
    df = pd.DataFrame(data)
    file_path = os.path.join(UPLOADS_DIR, 'admin_export.xlsx')
    df.to_excel(file_path, index=False)
    return file_path

def export_report_csv(filters):
    """Generates a CSV export for filtered performance reports"""
    data, _ = get_performance_overview(filters, limit=10000)
    df = pd.DataFrame(data)
    file_path = os.path.join(UPLOADS_DIR, 'report_export.csv')
    df.to_csv(file_path, index=False)
    return file_path

def export_report_pdf(filters, data):
    """Placeholder for PDF export - Returns CSV path for now due to dependency constraints"""
    return export_report_csv(filters)

def get_faculty_analytics(filters):
    """Computes pedagogical efficiency and success metrics for faculty benchmarking"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    where_clause = ""
    params = []
    if filters.get('department') and filters.get('department') != 'All':
        where_clause = " WHERE f.department = %s"
        params.append(filters.get('department'))
    
    query = f"""
        SELECT f.faculty_id, f.faculty_name, f.department,
               GROUP_CONCAT(DISTINCT sub.subject_name SEPARATOR ', ') as subjects_taught,
               AVG(m.total_marks) as avg_marks,
               (SUM(CASE WHEN m.total_marks >= 40 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(m.id), 0)) as pass_percentage
        FROM faculty f
        LEFT JOIN subjects sub ON f.faculty_id = sub.faculty_id
        LEFT JOIN marks m ON sub.subject_id = m.subject_id
        {where_clause}
        GROUP BY f.faculty_id
    """
    cursor.execute(query, params)
    data = cursor.fetchall()
    
    # Assign qualitative status
    for row in data:
        pct = float(row['pass_percentage'] or 0)
        row['status'] = 'Excellent' if pct >= 75 else 'Average' if pct >= 50 else 'Improvement Required'
        
    conn.close()
    return data

def get_single_faculty_detail(faculty_id):
    """Fetches high-density profile and performance data for a single faculty member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Profile & Global Stats
    cursor.execute("""
        SELECT f.*, 
               AVG(m.total_marks) as global_avg,
               COUNT(DISTINCT m.enrollment_no) as unique_students
        FROM faculty f
        LEFT JOIN subjects sub ON f.faculty_id = sub.faculty_id
        LEFT JOIN marks m ON sub.subject_id = m.subject_id
        WHERE f.faculty_id = %s
        GROUP BY f.faculty_id
    """, (faculty_id,))
    profile = cursor.fetchone()
    
    if not profile:
        conn.close()
        return None
        
    # Subject breakdown
    cursor.execute("""
        SELECT sub.subject_name, sub.semester,
               AVG(m.total_marks) as avg_marks,
               (SUM(CASE WHEN m.total_marks >= 40 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(m.id), 0)) as pass_pct,
               COUNT(m.id) as entry_count
        FROM subjects sub
        LEFT JOIN marks m ON sub.subject_id = m.subject_id
        WHERE sub.faculty_id = %s
        GROUP BY sub.subject_id
    """, (faculty_id,))
    subjects = cursor.fetchall()
    
    conn.close()
    return {'profile': profile, 'subjects': subjects}

def generate_faculty_performance_charts(data):
    """Legacy placeholder - Faculty charts are now rendered via Chart.js"""
    return True

def get_report_data(filters):
    """Generates complex analytical insights and aggregated data for institutional reporting"""
    from analysis import build_dashboard_conditions
    where_clause, values = build_dashboard_conditions(filters)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Dept performance
        cursor.execute(f"SELECT s.department, AVG(m.total_marks) as avg_marks FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.department", values)
        dept_perf = cursor.fetchall()

        # 2. Semester performance
        cursor.execute(f"SELECT s.semester, AVG(m.total_marks) as avg_marks FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.semester ORDER BY s.semester", values)
        sem_perf = cursor.fetchall()

        # 3. Subject performance
        cursor.execute(f"SELECT sub.subject_name, AVG(m.total_marks) as avg_marks FROM marks m JOIN subjects sub ON m.subject_id = sub.subject_id JOIN students s ON m.enrollment_no = s.enrollment_no {where_clause} GROUP BY sub.subject_name ORDER BY avg_marks DESC", values)
        sub_perf = cursor.fetchall()

        # 4. Success stats (Pass/Fail)
        cursor.execute(f"SELECT status, COUNT(*) as count FROM (SELECT CASE WHEN AVG(m.total_marks) >= 40 THEN 'PASS' ELSE 'FAIL' END as status FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.enrollment_no) as results GROUP BY status", values)
        pass_fail = cursor.fetchall()

        # 5. Attendance
        cursor.execute(f"SELECT status, COUNT(*) as count FROM attendance a JOIN students s ON a.enrollment_no = s.enrollment_no {where_clause} GROUP BY status", values)
        att_dist = cursor.fetchall()

        # 🧠 Calculate Insights
        all_avg = sum(r['avg_marks'] for r in sub_perf) / len(sub_perf) if sub_perf else 0
        pass_count = next((r['count'] for r in pass_fail if r['status'] == 'PASS'), 0)
        total_results = sum(r['count'] for r in pass_fail) or 1
        
        insights = {
            'avg_marks': round(all_avg, 2),
            'performance_label': 'Excellent' if all_avg > 75 else 'Progressing' if all_avg >= 50 else 'Critical Attention Required',
            'top_subject': sub_perf[0] if sub_perf else None,
            'weak_subject': sub_perf[-1] if sub_perf else None,
            'top_student': None, # Could add another query if needed
            'pass_percent': round((pass_count / total_results) * 100, 1),
            'low_performers_count': next((r['count'] for r in pass_fail if r['status'] == 'FAIL'), 0)
        }
        
        # Add top student to insights
        cursor.execute(f"SELECT s.name, AVG(m.total_marks) as avg_marks FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.enrollment_no, s.name ORDER BY avg_marks DESC LIMIT 1", values)
        insights['top_student'] = cursor.fetchone()

        return {
            'dept_perf': dept_perf,
            'sem_perf': sem_perf,
            'sub_perf': sub_perf,
            'pass_fail': pass_fail,
            'att_dist': att_dist,
            'insights': insights
        }
    except Exception as e:
        print(f"Report Data Error: {e}")
        return {'insights': {'avg_marks': 0, 'performance_label': 'N/A', 'pass_percent': 0, 'low_performers_count': 0}}
    finally:
        conn.close()

def generate_report_charts(data):
    """Legacy placeholder - Charts are now handled in the UI via Chart.js"""
    return True
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
    return [{'subject': r['subject'], 'internal': r['internal_marks'], 
             'viva': r['viva_marks'], 'external': r['external_marks'], 
             'total': r['total_marks']} for r in marks]

def calculate_student_summary(enrollment_no):
    marks = get_student_marks(enrollment_no)
    if not marks: return {'total_subjects': 0, 'avg_marks': 0}
    total_m = sum(m['total'] for m in marks)
    return {
        'total_subjects': len(marks),
        'avg_marks': round(total_m / len(marks), 2) if marks else 0
    }
