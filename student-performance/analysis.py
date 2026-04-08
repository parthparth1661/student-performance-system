import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import os
from db import get_db_connection

# Ensure vital directories exist for charts and exports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE_DIR, 'static', 'charts')
UPLOADS_DIR = os.path.join(BASE_DIR, 'static', 'uploads')

for directory in [CHARTS_DIR, UPLOADS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

DEPARTMENT_SUBJECTS = {
    'BCA': ['Python Programming', 'Java Programming', 'DBMS', 'Data Structures', 'Operating Systems', 'Web Technology'],
    'MCA': ['Advanced Python', 'Java', 'DBMS', 'DSA', 'Computer Networks', 'Software Engineering'],
    'B.TECH': ['Engineering Mathematics', 'Data Structures', 'DBMS', 'Operating Systems', 'Computer Networks', 'Software Engineering'],
    'M.TECH': ['Advanced Algorithms', 'Machine Learning', 'Cloud Computing', 'Distributed Systems', 'Data Mining', 'Research Methodology'],
    'MBA': ['Marketing Management', 'Financial Management', 'Human Resource Management', 'Operations Management', 'Business Analytics', 'Strategic Management']
}

def build_dashboard_conditions(filters={}):
    """Centralized high-precision filter builder for all analytical modules"""
    conditions = []
    values = []
    
    department = filters.get('department')
    semester = filters.get('semester')
    subject = filters.get('subject')
    search = filters.get('search')
    attendance_filter = filters.get('attendance')

    if department:
        conditions.append("s.department = %s")
        values.append(department)

    if semester:
        conditions.append("s.semester = %s")
        values.append(semester)

    if subject:
        # Join subjects to allow subject_name filtering
        conditions.append("sub.subject_name = %s")
        values.append(subject)

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
            HAVING (COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0)) < 75
        )
        """)
    elif attendance_filter == "high":
        conditions.append("""
        s.enrollment_no IN (
            SELECT enrollment_no 
            FROM attendance 
            GROUP BY enrollment_no 
            HAVING (COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0)) >= 75
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
        
        # 🎯 1. GET CENTRALIZED CONDITIONS
        where_clause, values = build_dashboard_conditions(filters)

        # 🥇 TOTAL STUDENTS
        cursor.execute(f"SELECT COUNT(*) as count FROM students s {where_clause}", values)
        total_students = cursor.fetchone()['count'] or 0
        
        # 🥈 TOTAL SUBJECTS (Context-Aware Calculation)
        department = filters.get('department')
        if department:
            cursor.execute("SELECT COUNT(*) as count FROM subjects WHERE department = %s", (department,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM subjects")
        total_subjects = cursor.fetchone()['count'] or 0
        
        # 🥉 AVERAGE MARKS
        avg_query = f"""
            SELECT AVG(m.marks_obtained) AS avg_marks 
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(avg_query, values)
        avg_marks = round(cursor.fetchone()['avg_marks'] or 0, 2)
        
        # 🏆 ATTENDANCE %
        attn_query = f"""
            SELECT (COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) 
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
            SELECT s.name, AVG(m.marks_obtained) as avg_marks
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

        # ⚠️ AT RISK COUNT (Below 75%)
        # Note: We strip the attendance input to count ALL defaulters within the ACTIVE context (Dept/Sem)
        risk_filters = filters.copy()
        risk_filters.pop('attendance', None)
        risk_where, risk_values = build_dashboard_conditions(risk_filters)
        
        # 🎯 Smart Base Logic for Syntax Robustness
        risk_base = risk_where if risk_where else " WHERE 1=1 "
        
        cursor.execute(f"""
            SELECT COUNT(DISTINCT s.enrollment_no) as count
            FROM students s
            LEFT JOIN subjects sub ON 1=1
            {risk_base}
            AND s.enrollment_no IN (
                SELECT enrollment_no FROM attendance 
                GROUP BY enrollment_no 
                HAVING (COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0)) < 75
            )
        """, risk_values)
        low_attendance_count = cursor.fetchone()['count'] or 0

        # --- CHART GENERATION IS NOW HANDLED BY generate_dashboard_charts() ---
        
        cursor.close()
        conn.close()
        return {
            'total_students': total_students, 'total_subjects': total_subjects,
            'avg_marks': avg_marks, 'attendance_percentage': attendance_percentage,
            'low_attendance_count': low_attendance_count, 'top_performer': top_performer
        }
    except Exception as e:
        print(f"Error in analytics suite: {e}")
        return {'total_students': 0, 'total_subjects': 0, 'avg_marks': 0, 'attendance_percentage': 0, 'low_attendance_count': 0, 'top_performer': "N/A"}

def generate_dashboard_charts(filters={}):
    """Generates 4 high-fidelity analytical charts for the admin dashboard"""
    conn = get_db_connection()
    if not conn: return {}
    
    # Ensure charts directory exists
    if not os.path.exists(CHARTS_DIR):
        os.makedirs(CHARTS_DIR)

    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        chart_paths = {
            'subject_avg': 'static/charts/subject_avg.png',
            'attendance_pie': 'static/charts/attendance_pie.png',
            'performance_trend': 'static/charts/performance_trend.png',
            'top_students': 'static/charts/top_students.png'
        }

        # 1. Subject-wise Average Marks (Bar Chart)
        bar_query = f"""
            SELECT sub.subject_name, AVG(m.marks_obtained) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN students s ON s.enrollment_no = m.enrollment_no
            {where_clause}
            GROUP BY sub.subject_name
        """
        cursor.execute(bar_query, values)
        bar_data = cursor.fetchall()

        plt.figure(figsize=(8, 5), dpi=100)
        plt.style.use('seaborn-v0_8-whitegrid')
        if bar_data:
            subjects = [row['subject_name'] for row in bar_data]
            marks = [float(row['avg_marks']) for row in bar_data]
            bars = plt.bar(subjects, marks, color='#6366f1', width=0.6, alpha=0.9)
            plt.title("Subject Performance Analysis", fontsize=12, fontweight='700', pad=20)
            plt.ylim(0, 100)
            plt.xticks(rotation=20, ha='right', fontsize=9)
            for bar in bars:
                yval = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f'{round(yval, 1)}', ha='center', va='bottom', fontsize=8, fontweight='bold')
        else:
            plt.text(0.5, 0.5, "Insufficient Data Records", ha='center', va='center', color='#94a3b8')
        plt.tight_layout()
        plt.savefig(os.path.join(BASE_DIR, chart_paths['subject_avg']), transparent=False, facecolor='white')
        plt.close()

        # 2. Attendance Distribution (Pie Chart)
        pie_query = f"""
            SELECT 
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance a
            JOIN students s ON s.enrollment_no = a.enrollment_no
            LEFT JOIN subjects sub ON a.subject_id = sub.subject_id
            {where_clause}
        """
        cursor.execute(pie_query, values)
        pie_data = cursor.fetchone()

        plt.figure(figsize=(6, 6), dpi=100)
        if pie_data and (pie_data['present'] or pie_data['absent']):
            labels = ['Present', 'Absent']
            sizes = [pie_data['present'] or 0, pie_data['absent'] or 0]
            colors = ['#10b981', '#ef4444']
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, 
                    startangle=140, pctdistance=0.85, wedgeprops={'edgecolor': 'white', 'linewidth': 2})
            centre_circle = plt.Circle((0,0), 0.70, fc='white')
            plt.gca().add_artist(centre_circle)
            plt.title("Attendance Distribution", fontsize=12, fontweight='700', pad=20)
        else:
            plt.text(0.5, 0.5, "No Records Found", ha='center', va='center', color='#94a3b8')
        plt.tight_layout()
        plt.savefig(os.path.join(BASE_DIR, chart_paths['attendance_pie']), transparent=False, facecolor='white')
        plt.close()

        # 3. Performance Trend (Line Chart)
        line_query = f"""
            SELECT exam_type, AVG(marks_obtained) as avg_marks
            FROM marks m
            JOIN students s ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY exam_type
            ORDER BY exam_type
        """
        cursor.execute(line_query, values)
        line_data = cursor.fetchall()

        plt.figure(figsize=(8, 5), dpi=100)
        if line_data:
            exams = [row['exam_type'] for row in line_data]
            marks = [float(row['avg_marks']) for row in line_data]
            plt.plot(exams, marks, marker='o', markersize=8, color='#6366f1', linewidth=3, markerfacecolor='white', markeredgewidth=2)
            plt.fill_between(exams, marks, alpha=0.1, color='#6366f1')
            plt.title("Institutional Performance Trend", fontsize=12, fontweight='700', pad=20)
            plt.ylim(0, 100)
            plt.grid(True, linestyle='--', alpha=0.5)
        else:
            plt.text(0.5, 0.5, "Insufficient Trend Data", ha='center', va='center', color='#94a3b8')
        plt.tight_layout()
        plt.savefig(os.path.join(BASE_DIR, chart_paths['performance_trend']), transparent=False, facecolor='white')
        plt.close()

        # 4. Top 5 Students (Bar Chart)
        top_query = f"""
            SELECT s.name, AVG(m.marks_obtained) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY s.name
            ORDER BY AVG(m.marks_obtained) DESC
            LIMIT 5
        """
        cursor.execute(top_query, values)
        top_data = cursor.fetchall()

        plt.figure(figsize=(8, 5), dpi=100)
        if top_data:
            names = [row['name'] for row in top_data]
            marks = [float(row['avg_marks']) for row in top_data]
            plt.bar(names, marks, color='#f59e0b', width=0.5, alpha=0.9)
            plt.title("Top 5 Performers", fontsize=12, fontweight='700', pad=20)
            plt.ylim(0, 100)
            plt.xticks(rotation=15, ha='right', fontsize=9)
            for i, v in enumerate(marks):
                plt.text(i, v + 2, str(round(v, 1)), ha='center', fontweight='bold', fontsize=8)
        else:
            plt.text(0.5, 0.5, "No Rankings Available", ha='center', va='center', color='#94a3b8')
        plt.tight_layout()
        plt.savefig(os.path.join(BASE_DIR, chart_paths['top_students']), transparent=False, facecolor='white')
        plt.close()

        cursor.close()
        conn.close()
        return chart_paths

    except Exception as e:
        print(f"Chart Engine Error: {e}")
        return {}


def get_performance_overview(filters={}, limit=10, offset=0):
    """Deep analytical student ledger with fully synchronized filtering and pagination"""
    conn = get_db_connection()
    if not conn: return [], 0
    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        # 1. Fetch Paginated Records
        query = f"""
            SELECT 
                s.enrollment_no,
                s.name,
                s.department,
                s.semester,
                sub.subject_name,
                AVG(m.marks_obtained) AS marks_obtained,
                (COUNT(CASE WHEN a.status='Present' THEN 1 END)*100.0/NULLIF(COUNT(a.attendance_id), 0)) AS attendance_percentage
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN attendance a ON s.enrollment_no = a.enrollment_no AND sub.subject_id = a.subject_id
            {where_clause}
            GROUP BY s.enrollment_no, s.name, s.department, s.semester, sub.subject_name
            ORDER BY s.enrollment_no ASC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, values + [limit, offset])
        data = cursor.fetchall()
        
        # 2. Count Total Records (for pagination logic)
        count_query = f"""
            SELECT COUNT(*) as total FROM (
                SELECT s.enrollment_no, sub.subject_id
                FROM students s
                JOIN marks m ON s.enrollment_no = m.enrollment_no
                JOIN subjects sub ON m.subject_id = sub.subject_id
                JOIN attendance a ON s.enrollment_no = a.enrollment_no AND sub.subject_id = a.subject_id
                {where_clause}
                GROUP BY s.enrollment_no, sub.subject_id
            ) as subquery
        """
        cursor.execute(count_query, values)
        total_records = cursor.fetchone()['total'] or 0
        
        cursor.close()
        conn.close()
        return data, total_records
    except Exception as e:
        print(f"Error in ledger overview: {e}")
        return [], 0

def generate_subject_avg_chart(subject_avg):
    """Generates an HD Subject-wise Average Marks Bar Chart"""
    plt.figure(figsize=(12, 6), dpi=200)
    
    if subject_avg:
        subjects = [row['subject'] for row in subject_avg]
        averages = [float(row['avg_marks']) if row['avg_marks'] is not None else 0 for row in subject_avg]
        
        bars = plt.bar(subjects, averages, color='#4F46E5', edgecolor='#3730A3', alpha=0.85, width=0.6)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1, round(yval, 1), 
                     ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1E293B')
    else:
        plt.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)

    plt.title('Subject-wise Average Marks', fontsize=16, fontweight='bold', pad=25)
    plt.xlabel('Subjects', fontsize=12, fontweight='bold')
    plt.ylabel('Average Marks', fontsize=12, fontweight='bold')
    plt.ylim(0, 110)
    plt.xticks(rotation=30, ha='right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'admin_subject_avg.png'), bbox_inches="tight")
    plt.close()

def generate_pass_fail_pie(pass_fail):
    """Generates an HD Pass/Fail Students Pie Chart"""
    plt.figure(figsize=(12, 6), dpi=200)
    
    if pass_fail and (pass_fail['pass_count'] or pass_fail['fail_count']):
        labels = ['Pass', 'Fail']
        sizes = [pass_fail['pass_count'], pass_fail['fail_count']]
        colors = ['#10B981', '#F43F5E']
        
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', 
                startangle=140, pctdistance=0.85, 
                wedgeprops={'linewidth': 3, 'edgecolor': 'white', 'antialiased': True})
        
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
    else:
        plt.text(0, 0, 'No Data Available', ha='center', va='center', fontsize=14)
        
    plt.title('Pass/Fail Distribution', fontsize=16, fontweight='bold', pad=25)
    plt.axis('equal') 
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'admin_pass_fail.png'), bbox_inches="tight")
    plt.close()

def generate_marks_distribution(all_marks):
    """Generates an HD Marks Distribution Histogram"""
    plt.figure(figsize=(12, 6), dpi=200)
    
    if all_marks:
        plt.hist(all_marks, bins=10, range=(0, 100), color='#8B5CF6', edgecolor='#7C3AED', alpha=0.8, rwidth=0.9)
    else:
        plt.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)
        
    plt.title('Student Marks Distribution', fontsize=16, fontweight='bold', pad=25)
    plt.xlabel('Marks (Range)', fontsize=12, fontweight='bold')
    plt.ylabel('Number of Students', fontsize=12, fontweight='bold')
    plt.xticks(range(0, 101, 10))
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'admin_distribution.png'), bbox_inches="tight")
    plt.close()

from datetime import datetime, timedelta

def get_working_days(department, semester):
    """Fallback function for working days (simplified for now)"""
    return 90 # Standard average academic term length
def process_csv(file_path, department=None, semester=None):
    try:
        df = pd.read_csv(file_path)
        # Normalize headers: strip, lower, and map roll_no -> enrollment_no 🎯
        cols = [c.strip().lower() for c in df.columns]
        df.columns = cols 
        if 'roll_no' in cols and 'enrollment_no' not in cols:
            df.rename(columns={'roll_no': 'enrollment_no'}, inplace=True)
            cols = list(df.columns)
        
        conn = get_db_connection()
        if not conn:
            return False, "Database connection failed."
        
        cursor = conn.cursor()
        success_count = 0
        errors = []
        
        # 1. STUDENTS CSV: enrollment_no, name, email, department, semester
        if all(x in cols for x in ['enrollment_no', 'name', 'email', 'department', 'semester']):
            from werkzeug.security import generate_password_hash
            
            for idx, row in df.iterrows():
                try:
                    # 🔐 Default password: enrollment_no + @123
                    default_pw = str(row['enrollment_no']) + "@123"
                    pw_hash = generate_password_hash(default_pw)
                    
                    cursor.execute("""
                        INSERT INTO students (enrollment_no, name, email, department, semester, password_hash, is_password_changed)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email), department=VALUES(department), semester=VALUES(semester)
                    """, (row['enrollment_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Student"

        # 2. MARKS CSV: enrollment_no, subject_id, exam_type, marks_obtained, total_marks
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'exam_type', 'marks_obtained']):
            for idx, row in df.iterrows():
                try:
                    total_marks = row.get('total_marks', 100)
                    cursor.execute("""
                        INSERT INTO marks (enrollment_no, subject_id, exam_type, marks_obtained, total_marks)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (row['enrollment_no'], row['subject_id'], row['exam_type'], row['marks_obtained'], total_marks))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Marks"

        # 3. ATTENDANCE CSV: enrollment_no, subject_id, date, status
        elif all(x in cols for x in ['enrollment_no', 'subject_id', 'date', 'status']):
            for idx, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO attendance (enrollment_no, subject_id, date, status)
                        VALUES (%s, %s, %s, %s)
                    """, (row['enrollment_no'], row['subject_id'], row['date'], row['status']))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Attendance"
            
        else:
            return False, "Unknown CSV format. Please check headers (enrollment_no, subject_id, etc.)"

        conn.commit()
        cursor.close()
        conn.close()
        
        if errors:
            return True, f"Imported {success_count} {msg_type} records. Errors: {'; '.join(errors[:3])}..."
        return True, f"Successfully imported {success_count} {msg_type} records."
        
    except Exception as e:
        return False, f"Error processing CSV: {str(e)}"

# --- Student Dashboard Helper Functions ---

def get_student_details(enrollment_no):
    """Fetches student profile details using enrollment number"""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        return student
    except Exception as e:
        print(f"Error fetching student details: {e}")
        return None

def get_student_marks(enrollment_no):
    """Fetches and aggregates marks for a student by subject"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT department FROM students WHERE enrollment_no = %s", (enrollment_no,))
        student = cursor.fetchone()
        if not student:
            conn.close()
            return []
        
        dept = student['department']

        # Fetch all marks for this student with subject details
        cursor.execute("""
            SELECT m.*, sub.subject_name 
            FROM marks m 
            JOIN subjects sub ON m.subject_id = sub.subject_id 
            WHERE m.enrollment_no = %s
        """, (enrollment_no,))
        marks_records = cursor.fetchall()
        cursor.close()
        conn.close()

        if not marks_records:
            return []

        df = pd.DataFrame(marks_records)
        
        subjects_data = []
        for subject_name in df['subject_name'].unique():
            subj_df = df[df['subject_name'] == subject_name]
            
            internal = subj_df[subj_df['exam_type'] == 'Internal']['marks_obtained'].sum()
            external = subj_df[subj_df['exam_type'] == 'External']['marks_obtained'].sum()
            
            practical = 0
            if dept == 'MBA':
                p_display = "N/A"
            else:
                practical = subj_df[subj_df['exam_type'] == 'Practical']['marks_obtained'].sum()
                p_display = int(practical)

            total = internal + external + practical
            
            has_external = not subj_df[subj_df['exam_type'] == 'External'].empty
            status = "PASS" if (has_external and external >= (subj_df[subj_df['exam_type'] == 'External']['total_marks'].iloc[0] * 0.35)) else "FAIL"
            
            suggestion = "" # Simplified
            subjects_data.append({
                'subject': subject_name,
                'internal': int(internal),
                'external': int(external),
                'practical': p_display,
                'total': int(total),
                'status': status,
                'suggestion': suggestion
            })
            
        return subjects_data
    except Exception as e:
        print(f"Error getting student marks: {e}")
        return []

def calculate_student_summary(enrollment_no):
    """Calculates summary statistics for a student"""
    subjects_data = get_student_marks(enrollment_no)
    if not subjects_data:
        return {
            'total_subjects': 0, 'total_marks': 0,
            'avg_marks': 0, 'overall_result': 'N/A'
        }
    
    total_subjects = len(subjects_data)
    aggregate_total = sum(item['total'] for item in subjects_data)
    avg_marks = aggregate_total / total_subjects if total_subjects > 0 else 0
    
    # Overall Result rule: If any subject has marks < 35 in External -> FAIL
    overall_result = "PASS"
    for item in subjects_data:
        if item['status'] == "FAIL":
            overall_result = "FAIL"
            break
            
    return {
        'total_subjects': total_subjects,
        'total_marks': aggregate_total,
        'avg_marks': round(avg_marks, 2),
        'overall_result': overall_result
    }

def generate_student_charts_new(enrollment_no):
    """Generates analytical charts for the student detail report"""
    subjects_data = get_student_marks(enrollment_no)
    
    # 📊 Chart 1: Subject-wise Total Marks (Professional Bar Chart)
    if subjects_data:
        plt.figure(figsize=(12, 6), dpi=200)
        subjects = [item['subject'] for item in subjects_data]
        totals = [item['total'] for item in subjects_data]
        
        plt.bar(subjects, totals, color='#6366f1', alpha=0.9, edgecolor='white', linewidth=1)
        
        plt.title('Subject-wise Performance Analysis', fontsize=18, fontweight='bold', pad=30, color='#1e293b')
        plt.xlabel('Academic Subjects', fontsize=12, fontweight='bold', color='#64748b')
        plt.ylabel('Total Marks Obtained', fontsize=12, fontweight='bold', color='#64748b')
        plt.xticks(rotation=20, ha='right', fontsize=10)
        plt.yticks(fontsize=10)
        plt.grid(axis='y', linestyle='--', alpha=0.4)
        plt.ylim(0, 105)
        
        # Add value labels on top of bars
        for i, v in enumerate(totals):
            plt.text(i, v + 2, str(v), ha='center', fontsize=10, fontweight='bold', color='#4f46e5')
            
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, f'student_{enrollment_no}_bar.png'), bbox_inches="tight")
        plt.close()

    # 🍕 Chart 2: Attendance Distribution (High-Fidelity Pie Chart)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance
            WHERE enrollment_no = %s
        """, (enrollment_no,))
        att_data = cursor.fetchone()
        present = att_data['present'] or 0
        absent = att_data['absent'] or 0
        
        plt.figure(figsize=(12, 7), dpi=200)
        if present + absent > 0:
            wedges, texts, autotexts = plt.pie(
                [present, absent], 
                labels=['Present', 'Absent'], 
                autopct='%1.1f%%',
                colors=['#10b981', '#ef4444'],
                startangle=140, 
                explode=(0.05, 0),
                wedgeprops={'edgecolor': 'white', 'linewidth': 3, 'antialiased': True}
            )
            plt.setp(autotexts, size=12, weight="bold", color="white")
            plt.setp(texts, size=12, weight="bold")
            plt.title('Attendance Distribution Overview', fontsize=18, fontweight='bold', pad=30, color='#1e293b')
        else:
            plt.text(0.5, 0.5, 'No Attendance Data Available', ha='center', va='center', fontsize=14, color='#94a3b8')
        
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, f'student_{enrollment_no}_pie.png'), bbox_inches="tight")
        plt.close()
        cursor.close()
        conn.close()

def export_student_report_excel(enrollment_no):
    """Exports student marks data to Excel"""
    student = get_student_details(enrollment_no)
    subjects_data = get_student_marks(enrollment_no)
    
    if not student or not subjects_data:
        return None
    
    df = pd.DataFrame(subjects_data)
    # Remove suggestion column for Excel if desired, or keep it. Let's keep it.
    
    file_name = f"Report_{enrollment_no}.xlsx"
    file_path = os.path.join(BASE_DIR, 'static', file_name)
    
    # Use ExcelWriter for formatting if needed, but basic to_excel is fine
    df.to_excel(file_path, index=False)
    return file_path

# --- Attendance Helper Functions ---

def get_attendance_summary():
    """Calculates student-wise attendance percentage"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                s.enrollment_no as roll_no, 
                s.name, 
                s.department, 
                s.semester,
                COUNT(a.attendance_id) as marked_days,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM students s
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
            GROUP BY s.enrollment_no
        """)
        summary = cursor.fetchall()
        
        # Cache working days to avoid repetitive DB calls
        working_days_cache = {}
        
        for s in summary:
            dept = s['department']
            sem = s['semester']
            key = (dept, sem)
            
            if key not in working_days_cache:
                working_days_cache[key] = get_working_days(dept, sem)
            
            total_working_days = working_days_cache[key]
            present = s['present_days'] or 0
            
            # If no calendar set, fall back to marked days or 0 to avoid division by zero
            denominator = total_working_days if total_working_days > 0 else (s['marked_days'] or 1)
            
            s['percentage'] = round((present / denominator * 100), 2)
            s['total_working_days'] = total_working_days
            
        cursor.close()
        conn.close()
        return summary
    except Exception as e:
        print(f"Error getting attendance summary: {e}")
        return []

# --- End Attendance Helper Functions ---

# --- End Student Dashboard Helper Functions ---

# --- Legacy Student-Specific Report Functions (Used by Admin) ---

def fetch_student_by_roll(roll_no):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        return student
    except Exception as e:
        print(f"Error fetching student: {e}")
        return None

def fetch_student_marks(student_id):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM marks WHERE student_id = %s ORDER BY exam_date", (student_id,))
        marks = cursor.fetchall()
        cursor.close()
        conn.close()
        return marks
    except Exception as e:
        print(f"Error fetching marks: {e}")
        return []

def calculate_student_stats(marks_list):
    if not marks_list:
        return None
    
    df = pd.DataFrame(marks_list)
    
    total_marks = df['marks'].sum()
    avg_marks = df['marks'].mean()
    percentage = avg_marks # Assuming max marks per subject is 100
    
    # Grade Calculation
    if percentage >= 80: grade = 'A'
    elif percentage >= 60: grade = 'B'
    elif percentage >= 50: grade = 'C'
    elif percentage >= 35: grade = 'D'
    else: grade = 'F'
    
    pass_status = "Pass" if avg_marks >= 35 else "Fail"
    
    # Insights
    strongest = df.loc[df['marks'].idxmax()]
    weakest = df.loc[df['marks'].idxmin()]
    
    suggestion = ""
    if weakest['marks'] < 35:
        suggestion = f"Needs urgent improvement in {weakest['subject']}. Consider remedial classes."
    elif percentage < 60:
        suggestion = "Consistent effort required across all subjects to improve overall percentage."
    else:
        suggestion = "Good performance! Keep it up."

    return {
        'total_marks': int(total_marks),
        'avg_marks': round(float(avg_marks), 2),
        'percentage': round(float(percentage), 2),
        'grade': grade,
        'pass_status': pass_status,
        'strongest_subject': strongest['subject'],
        'strongest_marks': int(strongest['marks']),
        'weakest_subject': weakest['subject'],
        'weakest_marks': int(weakest['marks']),
        'suggestion': suggestion
    }

def generate_student_charts(roll_no, name, marks_list):
    if not marks_list:
        return
    
    df = pd.DataFrame(marks_list)
    # Ensure marks is numeric
    df['marks'] = pd.to_numeric(df['marks'])
    
    # 1. Bar Chart: Subject-wise Marks
    plt.figure(figsize=(10, 5))
    plt.bar(df['subject'], df['marks'], color='steelblue')
    plt.title(f'Subject Wise Marks - {name}')
    plt.xlabel('Subjects')
    plt.ylabel('Marks')
    plt.ylim(0, 105)
    
    # Add labels on bars
    for i, v in enumerate(df['marks']):
        plt.text(i, v + 2, str(v), ha='center')
        
    bar_path = os.path.join(CHARTS_DIR, f'student_{roll_no}_bar.png')
    plt.savefig(bar_path)
    plt.close()

    # 2. Pie Chart: Pass/Fail Subjects
    pass_count = len(df[df['marks'] >= 35])
    fail_count = len(df[df['marks'] < 35])
    
    plt.figure(figsize=(6, 6))
    plt.pie([pass_count, fail_count], labels=['Pass', 'Fail'], 
            colors=['#28a745', '#dc3545'], autopct='%1.1f%%', startangle=90)
    plt.title('Pass vs Fail Subjects')
    pie_path = os.path.join(CHARTS_DIR, f'student_{roll_no}_pie.png')
    plt.savefig(pie_path)
    plt.close()

    # 3. Line Chart: Performance Trend (Exam Date vs Marks)
    if len(df) > 1:
        # Sort by date for proper trend
        df['exam_date'] = pd.to_datetime(df['exam_date'])
        df = df.sort_values('exam_date')
        
        plt.figure(figsize=(10, 5))
        plt.plot(df['exam_date'].dt.strftime('%Y-%m-%d'), df['marks'], marker='o', linestyle='-', color='orange')
        plt.title('Performance Trend')
        plt.xlabel('Date')
        plt.ylabel('Marks')
        plt.xticks(rotation=45)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        line_path = os.path.join(CHARTS_DIR, f'student_{roll_no}_line.png')
        plt.savefig(line_path)
        plt.close()

def clear_charts():
    """Deletes all generated PNG charts in the static/charts directory"""
    if os.path.exists(CHARTS_DIR):
        for file in os.listdir(CHARTS_DIR):
            if file.endswith('.png'):
                try:
                    os.remove(os.path.join(CHARTS_DIR, file))
                except Exception as e:
                    print(f"Error deleting chart {file}: {e}")
    print("All charts cleared successfully.")

def get_low_attendance_students(threshold=75):
    """Returns students with attendance percentage below threshold"""
    summary = get_attendance_summary()
    return [s for s in summary if s['percentage'] < threshold]

def get_weak_students_external(threshold=35):
    """Returns students who failed any subject in external exams"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.enrollment_no as roll_no, s.name, s.department, s.semester, COUNT(m.marks_id) as fail_count
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            WHERE m.exam_type = 'External' AND m.marks_obtained < (m.total_marks * 0.35)
            GROUP BY s.enrollment_no
            ORDER BY fail_count DESC
        """)
        weak_students = cursor.fetchall()
        cursor.close()
        conn.close()
        return weak_students
    except Exception as e:
        print(f"Error fetching weak students: {e}")
        return []

def export_admin_excel(department='All', semester='All'):
    """Generates a multi-sheet Excel report for the admin"""
    conn = get_db_connection()
    if not conn: return None
    
    try:
        # 1. Students Sheet
        query_s = "SELECT enrollment_no, name, email, department, semester FROM students WHERE 1=1"
        params_s = []
        if department != 'All':
            query_s += " AND department = %s"
            params_s.append(department)
        if semester != 'All':
            query_s += " AND semester = %s"
            params_s.append(semester)
        
        df_students = pd.read_sql(query_s, conn, params=params_s)
        
        # 2. Marks Sheet
        query_m = """
            SELECT m.enrollment_no, s.name, sub.subject_name, m.marks_obtained, m.total_marks, m.exam_type
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            WHERE 1=1
        """
        params_m = []
        if department != 'All':
            query_m += " AND s.department = %s"
            params_m.append(department)
        if semester != 'All':
            query_m += " AND s.semester = %s"
            params_m.append(semester)
            
        df_marks = pd.read_sql(query_m, conn, params=params_m)
        
        # 3. Attendance Sheet
        query_a = """
            SELECT a.enrollment_no, s.name, a.date, a.status
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            WHERE 1=1
        """
        params_a = []
        if department != 'All':
            query_a += " AND s.department = %s"
            params_a.append(department)
        if semester != 'All':
            query_a += " AND s.semester = %s"
            params_a.append(semester)
            
        df_attendance = pd.read_sql(query_a, conn, params=params_a)
        
        conn.close()
        
        file_path = os.path.join(BASE_DIR, 'static', 'admin_report.xlsx')
        with pd.ExcelWriter(file_path) as writer:
            df_students.to_excel(writer, sheet_name='Students', index=False)
            df_marks.to_excel(writer, sheet_name='Marks', index=False)
            df_attendance.to_excel(writer, sheet_name='Attendance', index=False)
            
        return file_path
    except Exception as e:
        print(f"Error exporting admin excel: {e}")
        return None

def export_student_excel(enrollment_no):
    """Generates a detailed Excel report for a specific student"""
    student = get_student_details(enrollment_no)
    marks_data = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    
    if not student or not marks_data:
        return None
        
    try:
        # Create DataFrames
        df_profile = pd.DataFrame([student])
        df_marks = pd.DataFrame(marks_data)
        df_summary = pd.DataFrame([summary])
        
        file_path = os.path.join(BASE_DIR, 'static', f'student_{enrollment_no}_report.xlsx')
        with pd.ExcelWriter(file_path) as writer:
            df_profile.to_excel(writer, sheet_name='Profile', index=False)
            df_marks.to_excel(writer, sheet_name='Subject Marks', index=False)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
        return file_path
    except Exception as e:
        print(f"Error exporting student excel: {e}")
        return None

def export_admin_excel(department='All', semester='All', subject='All', search=None, attendance=None):
    """Exports globally filtered performance overview to high-fidelity Excel report"""
    try:
        import pandas as pd
        filters = {
            'department': department if department != 'All' else None,
            'semester': semester if semester != 'All' else None,
            'subject': subject if subject != 'All' else None,
            'search': search,
            'attendance': attendance
        }
        data, _ = get_performance_overview(filters=filters, limit=5000) # High limit for export
        if not data: return None
        
        df = pd.DataFrame(data)
        # Professional Column Names
        df.columns = ['Student Name', 'Subject Name', 'Average Marks', 'Attendance %']
        
        file_name = f"admin_analytics_report_{date.today().strftime('%Y%m%d')}.xlsx"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)
            
        df.to_excel(file_path, index=False)
        return file_path
    except Exception as e:
        print(f"Error exporting analytical report: {e}")
        return None

def export_student_report_excel(roll_no):
    """Exports student internal assessment & performance report to Excel"""
    try:
        import pandas as pd
        details = get_student_details(roll_no)
        marks = get_student_marks(roll_no)
        summary = calculate_student_summary(roll_no)
        
        if not details or not marks: return None
        
        df_marks = pd.DataFrame(marks)
        df_summary = pd.DataFrame([summary])
        
        file_path = os.path.join(UPLOADS_DIR, f'student_{roll_no}_report.xlsx')
        if not os.path.exists(UPLOADS_DIR): os.makedirs(UPLOADS_DIR)
        
        with pd.ExcelWriter(file_path) as writer:
            df_marks.to_excel(writer, sheet_name='Performance', index=False)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
        return file_path
    except Exception as e:
        print(f"Error in student report export: {e}")
        return None

def generate_student_report_pdf(enrollment_no):
    """Generates a professional PDF performance report for a student"""
    try:
        from fpdf import FPDF
        from datetime import date
        
        student = get_student_details(enrollment_no)
        marks_list = get_student_marks(enrollment_no)
        summary = calculate_student_summary(enrollment_no)
        
        if not student: return None

        # --- FETCH ATTENDANCE DATA ---
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance
            WHERE enrollment_no = %s
        """, (enrollment_no,))
        att_summary = cursor.fetchone()
        
        total_classes = att_summary['total'] or 0
        present_days = att_summary['present'] or 0
        att_percent = round((present_days / total_classes * 100), 2) if total_classes > 0 else 0
        conn.close()

        class PDF(FPDF):
            def header(self):
                # Gradient-like header bar
                self.set_fill_color(99, 102, 241) # Indigo-600
                self.rect(0, 0, 210, 35, 'F')
                self.set_y(10)
                self.set_font('Helvetica', 'B', 22)
                self.set_text_color(255, 255, 255)
                self.cell(0, 10, ' STUDENT PERFORMANCE REPORT ', ln=True, align='C')
                self.set_font('Helvetica', 'I', 10)
                self.cell(0, 5, f'SPDA Academic System | Generated: {date.today().strftime("%d %B, %Y")}', ln=True, align='C')
                self.ln(10)

            def footer(self):
                self.set_y(-15)
                self.set_font('Helvetica', 'I', 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f'Page {self.page_no()} | This is a computer generated report', align='C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # 🟢 SECTION 1: STUDENT PROFILE
        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 10, '1. STUDENT PROFILE', ln=True)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(40, 8, 'Full Name:')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(60, 8, student['name'])
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 8, 'Enrollment No:')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(40, 8, student['enrollment_no'], ln=True)
        
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 8, 'Department:')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(60, 8, student['department'])
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(40, 8, 'Semester:')
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(40, 8, str(student['semester']), ln=True)
        pdf.ln(10)

        # 🟡 SECTION 2: PERFORMANCE KEY METRICS
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 10, '2. SYSTEM KPI SUMMARY', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # Draw summary boxes
        start_y = pdf.get_y()
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(10, start_y, 60, 25, 'F')
        pdf.rect(75, start_y, 60, 25, 'F')
        pdf.rect(140, start_y, 60, 25, 'F')
        
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(100, 116, 139)
        pdf.text(15, start_y + 8, 'AVERAGE SCORE')
        pdf.text(80, start_y + 8, 'ATTENDANCE')
        pdf.text(145, start_y + 8, 'RESULT STATUS')
        
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(99, 102, 241)
        pdf.text(15, start_y + 20, f'{summary["avg_marks"]}%')
        
        if att_percent < 75: pdf.set_text_color(239, 68, 68)
        else: pdf.set_text_color(16, 185, 129)
        pdf.text(80, start_y + 20, f'{att_percent}%')
        
        if summary["overall_result"] == 'PASS': pdf.set_text_color(16, 185, 129)
        else: pdf.set_text_color(239, 68, 68)
        pdf.text(145, start_y + 20, summary["overall_result"])
        
        pdf.set_y(start_y + 35)

        # 🔴 SECTION 3: ACADEMIC DETAILS TABLE
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 10, '3. SUBJECT-WISE BREAKDOWN', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Table Header
        pdf.set_fill_color(99, 102, 241)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(80, 10, ' Academic Subject', 0, 0, 'L', True)
        pdf.cell(30, 10, 'Internal', 0, 0, 'C', True)
        pdf.cell(30, 10, 'External', 0, 0, 'C', True)
        pdf.cell(25, 10, 'Total', 0, 0, 'C', True)
        pdf.cell(25, 10, 'Verdict', 0, 1, 'C', True)
        
        # Table Body
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(30, 41, 59)
        fill = False
        for item in marks_list:
            if fill: pdf.set_fill_color(248, 250, 252)
            else: pdf.set_fill_color(255, 255, 255)
            
            pdf.cell(80, 10, f' {item["subject"]}', 'B', 0, 'L', True)
            pdf.cell(30, 10, str(item["internal"]), 'B', 0, 'C', True)
            pdf.cell(30, 10, str(item["external"]), 'B', 0, 'C', True)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(25, 10, str(item["total"]), 'B', 0, 'C', True)
            
            if item["status"] == 'PASS': pdf.set_text_color(16, 185, 129)
            else: pdf.set_text_color(239, 68, 68)
            pdf.cell(25, 10, item["status"], 'B', 1, 'C', True)
            
            pdf.set_text_color(30, 41, 59)
            pdf.set_font('Helvetica', '', 10)
            fill = not fill
        
        pdf.ln(10)

        # 🔵 SECTION 4: ATTENDANCE & CONDUCT
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '4. ATTENDANCE & CONDUCT REMARKS', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'- Total Sessions Scheduled: {total_classes}', ln=True)
        pdf.cell(0, 8, f'- Physical Presence Recorded: {present_days} sessions', ln=True)
        pdf.cell(0, 8, f'- Unauthorized Absences: {att_summary["absent"] or 0} sessions', ln=True)
        
        pdf.ln(5)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(99, 102, 241)
        remark = "Exemplary Performance" if summary["avg_marks"] >= 85 and att_percent >= 85 else "Satisfactory" if summary["avg_marks"] >= 60 else "Requires Mentorship"
        pdf.cell(0, 10, f'Final Remark: {remark}', ln=True)

        file_name = f'Report_{enrollment_no}.pdf'
        file_path = os.path.join(UPLOADS_DIR, file_name)
        if not os.path.exists(UPLOADS_DIR): os.makedirs(UPLOADS_DIR)
        
        pdf.output(file_path)
        return file_path
        
    except Exception as e:
        print(f"Error in PDF generation layer: {e}")
        return None
