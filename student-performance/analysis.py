"""
SPDA Analytical Intelligence Engine
--------------------------------------
Centralized library for institutional data processing, performance metrics,
Chart.js data orchestration, and bulk CSV ingestion protocols.
"""

import pandas as pd
import os
from db import get_db_connection

# --- 1. ASSET CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Legacy path preservation; Dashboard now utilizes web-native Chart.js engine
CHARTS_DIR = os.path.join(BASE_DIR, 'static', 'charts')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')

# Ensure vital asset directories exist for system stability
for directory in [CHARTS_DIR, UPLOADS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)


# --- 2. DYNAMIC CONDITION BUILDER ---

def build_dashboard_conditions(filters={}):
    """
    Centralized high-precision filter builder for all analytical modules.
    Standardizes filtering across students, marks, and attendance registries.
    """
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
        # Dual-vector search: Name or Identity
        conditions.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
        values.append(f"%{search}%")
        values.append(f"%{search}%")

    if attendance_filter == "low":
        # Institutional Alert: Filter students with attendance < 75%
        conditions.append("""
        s.enrollment_no IN (
            SELECT enrollment_no FROM attendance 
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


# --- 3. DASHBOARD KPI METRICS ---

def get_dashboard_stats(filters={}):
    """
    Computes top-level institutional KPIs for the administrative nexus.
    Returns: Total Students, Avg Marks, Attendance Success Rate, Risk Alerts.
    """
    conn = get_db_connection()
    if not conn: return {}
    
    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        # 1. Enrollment & Course metrics
        cursor.execute(f"SELECT COUNT(DISTINCT s.enrollment_no) as total FROM students s {where_clause}", values)
        count_data = cursor.fetchone()
        
        cursor.execute(f"SELECT COUNT(DISTINCT sub.subject_id) as total FROM subjects sub JOIN students s ON sub.department = s.department {where_clause}", values)
        sub_data = cursor.fetchone()
        
        # 2. Performance Mean
        cursor.execute(f"SELECT AVG(m.total_marks) as avg_marks FROM marks m JOIN students s ON m.enrollment_no = s.enrollment_no JOIN subjects sub ON m.subject_id = sub.subject_id {where_clause}", values)
        perf_data = cursor.fetchone()
        
        # 3. Attendance Success Rate
        cursor.execute(f"SELECT (COUNT(CASE WHEN a.status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0)) as att_pct FROM attendance a JOIN students s ON a.enrollment_no = s.enrollment_no LEFT JOIN subjects sub ON a.subject_id = sub.subject_id {where_clause}", values)
        att_data = cursor.fetchone()
        
        # 4. Contextual Insights (Risk & Peaks)
        cursor.execute(f"SELECT COUNT(*) as count FROM (SELECT s.enrollment_no FROM students s JOIN attendance a ON s.enrollment_no = a.enrollment_no {where_clause} GROUP BY s.enrollment_no HAVING (COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0)) < 75) as risks", values)
        risk_data = cursor.fetchone()
        
        cursor.execute(f"SELECT s.name FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no JOIN subjects sub ON m.subject_id = sub.subject_id {where_clause} ORDER BY m.total_marks DESC LIMIT 1", values)
        top_data = cursor.fetchone()

        stats = {
            'total_students': count_data['total'] or 0,
            'total_subjects': sub_data['total'] or 0,
            'avg_marks': round(float(perf_data['avg_marks'] or 0), 1),
            'attendance_percentage': round(float(att_data['att_pct'] or 0), 1),
            'low_attendance_count': risk_data['count'] or 0,
            'top_performer': top_data['name'] if top_data else 'N/A'
        }
        conn.close()
        return stats
    except Exception as e:
        print(f"Stats Matrix Error: {e}")
        return {}


# --- 4. CHART.JS ORCHESTRATION ---

def get_dashboard_chart_data(filters={}):
    """
    Returns high-density analytical JSON payloads for web-native Chart.js rendering.
    Encompasses Subject Averages, Result Distribution, and Performance Components.
    """
    conn = get_db_connection()
    if not conn: return {}

    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        analytics = {
            'subject_avg': {'labels': [], 'values': []},
            'results_dist': {'labels': ['Pass', 'Fail'], 'values': [0, 0]},
            'attendance_dist': {'labels': ['Present', 'Absent'], 'values': [0, 0]},
            'performance_trend': {'labels': ['Internal Unit', 'Viva Board', 'End Term'], 'values': []}
        }

        # 1. Subject-wise performance comparision
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

        # 2. Results Success Distribution
        cursor.execute(f"SELECT SUM(CASE WHEN m.total_marks >= 40 THEN 1 ELSE 0 END) as pass_count, SUM(CASE WHEN m.total_marks < 40 THEN 1 ELSE 0 END) as fail_count FROM marks m JOIN students s ON m.enrollment_no = s.enrollment_no JOIN subjects sub ON m.subject_id = sub.subject_id {where_clause}", values)
        data = cursor.fetchone()
        if data:
            analytics['results_dist']['values'] = [int(data['pass_count'] or 0), int(data['fail_count'] or 0)]

        # 3. Performance Components (Modular Breakdown)
        cursor.execute(f"SELECT AVG(m.internal_marks) as Internal, AVG(m.viva_marks) as Viva, AVG(m.external_marks) as External FROM marks m JOIN students s ON m.enrollment_no = s.enrollment_no JOIN subjects sub ON m.subject_id = sub.subject_id {where_clause}", values)
        data = cursor.fetchone()
        if data:
            analytics['performance_trend']['values'] = [round(float(data['Internal'] or 0), 1), round(float(data['Viva'] or 0), 1), round(float(data['External'] or 0), 1)]

        conn.close()
        return analytics
    except Exception as e:
        print(f"Chart Analytics Error: {e}")
        return {}


# --- 5. BULK DATA INGESTION ---

def process_csv(file_path):
    """
    Institutional Data Gateway: Parses bulk CSV uploads and synchronizes
    with Students, Attendance, or Marks registries using auto-detection.
    """
    try:
        df = pd.read_csv(file_path)
        cols = [c.strip().lower() for c in df.columns]
        df.columns = cols 
        
        # Legacy Support: Map Roll No to Enrollment
        if 'roll_no' in cols and 'enrollment_no' not in cols:
            df.rename(columns={'roll_no': 'enrollment_no'}, inplace=True)
            cols = list(df.columns)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        success_count = 0
        
        # Identity Mapping: Students Registry
        if all(x in cols for x in ['enrollment_no', 'name', 'email', 'department', 'semester']):
            from werkzeug.security import generate_password_hash
            for _, row in df.iterrows():
                pw_hash = generate_password_hash(str(row['enrollment_no']))
                cursor.execute("""
                    INSERT INTO students (enrollment_no, name, email, department, semester, password_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email), department=VALUES(department)
                """, (row['enrollment_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
                success_count += 1
                
        # Activity Mapping: Global Attendance
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'date', 'status']):
            for _, row in df.iterrows():
                cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)", (row['enrollment_no'], row['subject_id'], row['date'], row['status']))
                success_count += 1
                
        # Outcome Mapping: Academic Marks
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'internal', 'viva', 'external']):
            for _, row in df.iterrows():
                i, v, e = int(row['internal']), int(row['viva']), int(row['external'])
                total = i + v + e
                cursor.execute("""
                    INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks, result)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE internal_marks=VALUES(internal_marks), viva_marks=VALUES(viva_marks), 
                                         external_marks=VALUES(external_marks), total_marks=VALUES(total_marks), result=VALUES(result)
                """, (row['enrollment_no'], row['subject_id'], i, v, e, total, 'Pass' if total >= 40 else 'Fail'))
                success_count += 1
        else:
            return False, "Synchronization Failed: Ledger Header Format Unrecognized."

        conn.commit()
        conn.close()
        return True, f"Operation Successful: {success_count} institutional records synchronized."
    except Exception as e:
        return False, f"System Fault: {str(e)}"


# --- 6. FACULTY ANALYTICAL MODULES ---

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
    
    # Assign qualitative status labels
    for row in data:
        pct = float(row['pass_percentage'] or 0)
        row['status'] = 'Excellent' if pct >= 75 else 'Average' if pct >= 50 else 'Improvement Required'
        
    conn.close()
    return data

def get_single_faculty_detail(faculty_id):
    """Fetches high-density profile and performance data for a single faculty member"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Identity & Cumulative Stats
    cursor.execute("""
        SELECT f.*, AVG(m.total_marks) as global_avg, COUNT(DISTINCT m.enrollment_no) as unique_students
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
        
    # 2. Subject Breakdown Matrix
    cursor.execute("""
        SELECT sub.subject_name, sub.semester, AVG(m.total_marks) as avg_marks,
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


# --- 7. INSTITUTIONAL REPORTING ---

def get_report_data(filters):
    """Generates complex analytical insights and aggregated data for qualitative institutional reporting"""
    where_clause, values = build_dashboard_conditions(filters)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Dept-wise comparative benchmarking
        cursor.execute(f"SELECT s.department, AVG(m.total_marks) as avg_marks FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.department", values)
        dept_perf = cursor.fetchall()

        # Subject-wise efficacy matrix
        cursor.execute(f"SELECT sub.subject_name, AVG(m.total_marks) as avg_marks FROM marks m JOIN subjects sub ON m.subject_id = sub.subject_id JOIN students s ON m.enrollment_no = s.enrollment_no {where_clause} GROUP BY sub.subject_name ORDER BY avg_marks DESC", values)
        sub_perf = cursor.fetchall()

        # Success Index (Pass/Fail)
        cursor.execute(f"SELECT status, COUNT(*) as count FROM (SELECT CASE WHEN AVG(m.total_marks) >= 40 THEN 'PASS' ELSE 'FAIL' END as status FROM students s JOIN marks m ON s.enrollment_no = m.enrollment_no {where_clause} GROUP BY s.enrollment_no) as results GROUP BY status", values)
        pass_fail = cursor.fetchall()

        # Insight Synthesis
        sub_list = [r['avg_marks'] for r in sub_perf]
        all_avg = sum(sub_list) / len(sub_list) if sub_list else 0
        
        return {
            'dept_perf': dept_perf,
            'sub_perf': sub_perf,
            'pass_fail': pass_fail,
            'avg_marks': round(all_avg, 1)
        }
    except Exception as e:
        print(f"Reporting Fault: {e}")
        return {}
    finally:
        conn.close()

def export_report_csv(filters):
    """Generates an institution-ready CSV export for filtered performance reports"""
    # Logic preservation for future CSV export enhancements
    pass

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
