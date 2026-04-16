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
                HAVING COALESCE(COUNT(CASE WHEN status='Present' THEN 1 END)*100.0/NULLIF(COUNT(*), 0), 0) < 75
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
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
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
            
            # --- IMPROVEMENTS 🔥 ---
            plt.title("Subject-wise Marks", fontsize=13, fontweight='bold', pad=15)
            plt.xlabel("Subjects", fontsize=10, fontweight='600')
            plt.ylabel("Average Marks (%)", fontsize=10, fontweight='600')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.ylim(0, 110)
            plt.xticks(rotation=20, ha='right', fontsize=9)
            
            # Show values and highlight TOP
            max_val = max(marks) if marks else 0
            for i, v in enumerate(marks):
                plt.text(i, v + 1.5, f'{round(v, 1)}', ha='center', fontsize=9, fontweight='bold', color='#1e293b')
                if v == max_val and v > 0:
                    plt.text(i, v + 6, "TOP", ha='center', fontsize=8, fontweight='900', color='#4f46e5', 
                             bbox=dict(facecolor='white', alpha=0.8, edgecolor='#6366f1', boxstyle='round,pad=0.2'))
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

        # 3. Performance Trend (Simplified to Subjects)
        line_query = f"""
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
            FROM marks m
            JOIN students s ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY sub.subject_name
            ORDER BY sub.subject_name
        """
        cursor.execute(line_query, values)
        line_data = cursor.fetchall()
        
        # 4. Top Students (Leaderboard)
        top_query = f"""
            SELECT s.name, AVG(m.total_marks) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            {where_clause}
            GROUP BY s.enrollment_no
            ORDER BY avg_marks DESC
            LIMIT 5
        """
        cursor.execute(top_query, values)
        top_data = cursor.fetchall()

        cursor.close()
        conn.close()
        return chart_paths
    except Exception as e:
        print(f"Chart generation error: {e}")
        return {}
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

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
                AVG(m.total_marks) AS marks_obtained,
                COALESCE(COUNT(CASE WHEN a.status='Present' THEN 1 END)*100.0/NULLIF(COUNT(a.attendance_id), 0), 0) AS attendance_percentage
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no AND sub.subject_id = a.subject_id
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
                LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no AND sub.subject_id = a.subject_id
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
        
        # --- IMPROVEMENTS 🔥 ---
        plt.title('Subject-wise Average Marks', fontsize=16, fontweight='bold', pad=25)
        plt.xlabel('Subjects', fontsize=12, fontweight='bold')
        plt.ylabel('Average Marks', fontsize=12, fontweight='bold')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.ylim(0, 115)
        plt.xticks(rotation=30, ha='right', fontsize=10)
        
        # Show values and highlight TOP
        max_val = max(averages) if averages else 0
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1.5, round(yval, 1), 
                     ha='center', va='bottom', fontsize=10, fontweight='bold', color='#1E293B')
            if yval == max_val and yval > 0:
                 plt.text(bar.get_x() + bar.get_width()/2, yval + 6, "BEST", ha='center', fontsize=9, fontweight='bold', color='#4F46E5')
    else:
        plt.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)

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
        n, bins, patches = plt.hist(all_marks, bins=10, range=(0, 100), color='#8B5CF6', edgecolor='#7C3AED', alpha=0.8, rwidth=0.9)
        # Add labels to histogram bins
        for i in range(len(n)):
            if n[i] > 0:
                plt.text(bins[i] + (bins[i+1]-bins[i])/2, n[i] + 0.2, int(n[i]), ha='center', fontweight='bold')
    else:
        plt.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)
        
    plt.title('Student Marks Distribution', fontsize=16, fontweight='bold', pad=25)
    plt.xlabel('Marks (Range)', fontsize=12, fontweight='bold')
    plt.ylabel('Number of Students', fontsize=12, fontweight='bold')
    plt.xticks(range(0, 101, 10))
    plt.grid(axis='y', linestyle='--', alpha=0.7)
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
                    # 🛡️ Default Protocol: password = enrollment_no
                    pw_hash = generate_password_hash(str(row['enrollment_no']))
                    
                    cursor.execute("""
                        INSERT INTO students (enrollment_no, name, email, department, semester, password_hash, is_password_changed)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email), department=VALUES(department), semester=VALUES(semester)
                    """, (row['enrollment_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Student"

        # 2. MARKS CSV: enrollment_no, subject, department, semester, internal_marks, viva_marks, external_marks
        elif all(x in cols for x in ['enrollment_no', 'subject', 'department', 'semester', 'internal_marks', 'viva_marks', 'external_marks']):
            for idx, row in df.iterrows():
                try:
                    # 🎯 Get subject_id using (subject + department + semester)
                    cursor.execute("""
                        SELECT subject_id FROM subjects 
                        WHERE subject_name = %s AND department = %s AND semester = %s
                    """, (row['subject'], row['department'], row['semester']))
                    sub_res = cursor.fetchone()
                    
                    if not sub_res:
                        errors.append(f"Row {idx+2}: Subject '{row['subject']}' not found in catalog.")
                        continue
                        
                    subject_id = sub_res[0]
                    
                    # 🎯 Validate student exists using enrollment_no
                    cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no = %s", (row['enrollment_no'],))
                    if not cursor.fetchone():
                        errors.append(f"Row {idx+2}: Student '{row['enrollment_no']}' not registered.")
                        continue
                        
                    i_m = int(row['internal_marks'])
                    v_m = int(row['viva_marks'])
                    e_m = int(row['external_marks'])
                    total_m = i_m + v_m + e_m
                    
                    # 🧱 STEP 3 — INSERT / UPDATE LOGIC (Duplicate Prevention via ON DUPLICATE KEY)
                    # Note: We need a unique constraint on (enrollment_no, subject_id) for this to work correctly
                    # or check manually.
                    cursor.execute("SELECT id FROM marks WHERE enrollment_no = %s AND subject_id = %s", (row['enrollment_no'], subject_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute("""
                            UPDATE marks 
                            SET internal_marks=%s, viva_marks=%s, external_marks=%s, total_marks=%s 
                            WHERE id=%s
                        """, (i_m, v_m, e_m, total_m, existing[0]))
                    else:
                        cursor.execute("""
                            INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (row['enrollment_no'], subject_id, i_m, v_m, e_m, total_m))
                    
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Marks (Breakdown)"

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
    """Fetches and aggregates marks for a student by subject using the new schema"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        # 🛡️ Enrollment-Locked Query
        cursor.execute("""
            SELECT m.*, sub.subject_name 
            FROM marks m 
            JOIN subjects sub ON m.subject_id = sub.subject_id 
            WHERE m.enrollment_no = %s
        """, (enrollment_no,))
        marks_records = cursor.fetchall()
        cursor.close()
        conn.close()

        subjects_data = []
        for row in marks_records:
            total = row['total_marks']
            status = "PASS" if total >= 40 else "FAIL"
            
            subjects_data.append({
                'subject': row['subject_name'],
                'internal': row['internal_marks'],
                'viva': row['viva_marks'],
                'external': row['external_marks'],
                'total': total,
                'status': status,
                'suggestion': "Consistent effort required." if total < 60 else "Good performance."
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
    
    # Overall Result rule: If avg marks < 40 -> FAIL
    overall_result = "PASS"
    if avg_marks < 40:
        overall_result = "FAIL"
            
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
        
        bars = plt.bar(subjects, totals, color='#6366f1', alpha=0.9, edgecolor='white', linewidth=1)
        
        # --- IMPROVEMENTS 🔥 ---
        plt.title('Subject-wise Performance Analysis', fontsize=18, fontweight='bold', pad=30, color='#1e293b')
        plt.xlabel('Academic Subjects', fontsize=12, fontweight='bold', color='#64748b')
        plt.ylabel('Total Marks Obtained', fontsize=12, fontweight='bold', color='#64748b')
        plt.xticks(rotation=20, ha='right', fontsize=10)
        plt.yticks(fontsize=10)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.ylim(0, 115)
        
        # Add value labels on top of bars and highlight BEST
        max_val = max(totals) if totals else 0
        for i, v in enumerate(totals):
            plt.text(i, v + 2, str(v), ha='center', fontsize=10, fontweight='bold', color='#4f46e5')
            if v == max_val and v > 0:
                plt.text(i, v + 7, "BEST SCORE", ha='center', fontsize=9, fontweight='bold', color='#6366f1',
                         bbox=dict(facecolor='white', alpha=0.9, edgecolor='#6366f1', boxstyle='round,pad=0.3'))
            
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
            SELECT s.enrollment_no as roll_no, s.name, s.department, s.semester, COUNT(m.id) as fail_count
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            WHERE m.total_marks < 35
            GROUP BY s.enrollment_no
            ORDER BY fail_count DESC
        """, ())
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
            SELECT m.enrollment_no, s.name, sub.subject_name, m.internal_marks, m.viva_marks, m.external_marks, m.total_marks
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

def get_report_data(filters={}):
    """Aggregate all statistical data required for the high-fidelity reports page"""
    conn = get_db_connection()
    if not conn: 
        return {
            'dept_perf': [], 'sem_perf': [], 'sub_perf': [],
            'pass_fail': {'pass_count': 0, 'fail_count': 0},
            'attendance': {'present': 0, 'absent': 0},
            'insights': {
                'avg_marks': 0, 'performance_label': 'Infrastructure Error',
                'top_subject': None, 'weak_subject': None,
                'pass_percent': 0, 'fail_percent': 0,
                'top_student': None, 'low_performers_count': 0
            }
        }
    
    try:
        cursor = conn.cursor(dictionary=True)
        where_clause, values = build_dashboard_conditions(filters)
        
        # 🟢 1. DEPARTMENT-WISE PERFORMANCE
        cursor.execute(f"""
            SELECT s.department, AVG(m.total_marks) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            {where_clause}
            GROUP BY s.department
        """, values)
        dept_perf = cursor.fetchall()
        
        # 🟡 2. SEMESTER-WISE PERFORMANCE
        cursor.execute(f"""
            SELECT s.semester, AVG(m.total_marks) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            {where_clause}
            GROUP BY s.semester
            ORDER BY s.semester
        """, values)
        sem_perf = cursor.fetchall()
        
        # 🔴 3. SUBJECT-WISE PERFORMANCE
        cursor.execute(f"""
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN students s ON m.enrollment_no = s.enrollment_no
            {where_clause}
            GROUP BY sub.subject_name
            ORDER BY avg_marks DESC
            LIMIT 10
        """, values)
        sub_perf = cursor.fetchall()
        
        # 🔵 4. PASS/FAIL RATIO
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN m.external_marks >= 21 THEN 1 ELSE 0 END) as pass_count,
                SUM(CASE WHEN m.external_marks < 21 THEN 1 ELSE 0 END) as fail_count
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            {where_clause}
        """, values)
        pass_fail = cursor.fetchone()
        
        # 🟣 5. ATTENDANCE SUMMARY
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            {where_clause}
        """, values)
        attendance = cursor.fetchone()
        
        # 🏥 6. AUTO-INSIGHTS ENGINE (NEW 🔥)
        insights = {}
        
        # A. Overall performance
        cursor.execute(f"""
            SELECT AVG(m.total_marks) as avg 
            FROM marks m 
            JOIN students s ON m.enrollment_no = s.enrollment_no 
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
        """, values)
        avg_val = cursor.fetchone()['avg'] or 0
        insights['avg_marks'] = round(avg_val, 2)
        if avg_val > 75: insights['performance_label'] = "Excellent overall performance"
        elif avg_val >= 50: insights['performance_label'] = "Average performance"
        else: insights['performance_label'] = "Performance needs improvement"

        # B. Top performing subject
        cursor.execute(f"""
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN students s ON m.enrollment_no = s.enrollment_no
            {where_clause}
            GROUP BY sub.subject_id
            ORDER BY avg_marks DESC
            LIMIT 1
        """, values)
        insights['top_subject'] = cursor.fetchone()

        # C. Weak subject detection
        cursor.execute(f"""
            SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN students s ON m.enrollment_no = s.enrollment_no
            {where_clause}
            GROUP BY sub.subject_id
            ORDER BY avg_marks ASC
            LIMIT 1
        """, values)
        insights['weak_subject'] = cursor.fetchone()

        # D. Pass/Fail Analysis
        if pass_fail and (pass_fail['pass_count'] or pass_fail['fail_count']):
            total = (pass_fail['pass_count'] or 0) + (pass_fail['fail_count'] or 0)
            insights['pass_percent'] = round((pass_fail['pass_count'] or 0) / total * 100, 1) if total > 0 else 0
            insights['fail_percent'] = round((pass_fail['fail_count'] or 0) / total * 100, 1) if total > 0 else 0
        
        # E. Top student
        cursor.execute(f"""
            SELECT s.name, AVG(m.total_marks) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY s.enrollment_no, s.name
            ORDER BY avg_marks DESC
            LIMIT 1
        """, values)
        insights['top_student'] = cursor.fetchone()

        # F. Low performers (Below 40)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT m.enrollment_no) as count
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            AND m.total_marks < 40
        """, values)
        insights['low_performers_count'] = cursor.fetchone()['count'] or 0


        return {
            'dept_perf': dept_perf,
            'sem_perf': sem_perf,
            'sub_perf': sub_perf,
            'pass_fail': pass_fail,
            'attendance': attendance,
            'insights': insights
        }
    except Exception as e:
        print(f"Error fetching report data: {e}")
        return {
            'dept_perf': [], 'sem_perf': [], 'sub_perf': [],
            'pass_fail': {'pass_count': 0, 'fail_count': 0},
            'attendance': {'present': 0, 'absent': 0},
            'insights': {
                'avg_marks': 0, 'performance_label': 'Data Unavailable',
                'top_subject': None, 'weak_subject': None,
                'pass_percent': 0, 'fail_percent': 0,
                'top_student': None, 'low_performers_count': 0
            }
        }
    finally:
        conn.close()

def generate_report_charts(data, suffix='report'):
    """Generate the full analytical suite of charts for the reporting engine"""
    try:
        from datetime import date
        plt.style.use('ggplot')
        
        # 1. Department-wise Performance (Bar)
        if data.get('dept_perf'):
            plt.figure(figsize=(10, 6))
            depts = [d['department'] for d in data['dept_perf']]
            marks = [float(d['avg_marks']) for d in data['dept_perf']]
            bars = plt.bar(depts, marks, color='#6366f1', alpha=0.8, edgecolor='#4f46e5', linewidth=1.5)
            plt.title('Performance benchmarking by Department', fontsize=14, fontweight='bold', pad=20)
            plt.ylabel('Average Marks Aggregate (%)', fontweight='bold')
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            # Add labels
            for bar in bars:
                yval = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f'{yval:.1f}%', ha='center', va='bottom', fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(CHARTS_DIR, f'{suffix}_dept.png'), dpi=200)
            plt.close()

        # 2. Semester trend (Line)
        if data.get('sem_perf'):
            plt.figure(figsize=(10, 6))
            sems = [f"Sem {d['semester']}" for d in data['sem_perf']]
            marks = [float(d['avg_marks']) for d in data['sem_perf']]
            plt.plot(sems, marks, marker='o', linestyle='-', color='#ec4899', linewidth=3, markersize=8, markerfacecolor='white', markeredgewidth=2)
            plt.fill_between(sems, marks, color='#fbcfe8', alpha=0.3)
            plt.title('Academic Growth Curve across Semesters', fontsize=14, fontweight='bold', pad=20)
            plt.ylabel('Average Score (%)', fontweight='bold')
            plt.grid(True, linestyle=':', alpha=0.6)
            plt.tight_layout()
            plt.savefig(os.path.join(CHARTS_DIR, f'{suffix}_sem.png'), dpi=200)
            plt.close()

        # 3. Subject Distribution (Horizontal Bar)
        if data.get('sub_perf'):
            plt.figure(figsize=(10, 6))
            subs = [d['subject_name'][:15] + '...' if len(d['subject_name']) > 15 else d['subject_name'] for d in data['sub_perf']]
            marks = [float(d['avg_marks']) for d in data['sub_perf']]
            plt.barh(subs, marks, color='#10b981', alpha=0.8)
            plt.title('Top 10 High-Performing Subjects', fontsize=14, fontweight='bold', pad=20)
            plt.xlabel('Average Marks (%)', fontweight='bold')
            plt.gca().invert_yaxis()
            plt.tight_layout()
            plt.savefig(os.path.join(CHARTS_DIR, f'{suffix}_sub.png'), dpi=200)
            plt.close()

        # 4. Pass/Fail Success Ratio (Donut)
        if data.get('pass_fail'):
            pf = data['pass_fail']
            counts = [pf['pass_count'] or 0, pf['fail_count'] or 0]
            if sum(counts) > 0:
                plt.figure(figsize=(8, 8))
                plt.pie(counts, labels=['Pass', 'Fail'], autopct='%1.1f%%', colors=['#10b981', '#ef4444'], 
                        startangle=140, pctdistance=0.85, wedgeprops={'width': 0.4, 'edgecolor': 'w'})
                plt.title('Institutional Pass/Fail Velocity', fontsize=14, fontweight='bold', pad=10)
                plt.tight_layout()
                plt.savefig(os.path.join(CHARTS_DIR, f'{suffix}_pf.png'), dpi=200)
                plt.close()

        # 5. Attendance Distribution (Donut)
        if data.get('attendance'):
            att = data['attendance']
            counts = [att['present'] or 0, att['absent'] or 0]
            if sum(counts) > 0:
                plt.figure(figsize=(8, 8))
                plt.pie(counts, labels=['Present', 'Absent'], autopct='%1.1f%%', colors=['#6366f1', '#f97316'], 
                        startangle=140, pctdistance=0.85, wedgeprops={'width': 0.4, 'edgecolor': 'w'})
                plt.title('Campus Engagement (Attendance)', fontsize=14, fontweight='bold', pad=10)
                plt.tight_layout()
                plt.savefig(os.path.join(CHARTS_DIR, f'{suffix}_att.png'), dpi=200)
                plt.close()

        return True
    except Exception as e:
        print(f"Error generating report charts: {e}")
        return False

def export_report_csv(filters={}):
    """Export the filtered raw data to CSV for tabular analysis"""
    try:
        from datetime import date
        where_clause, values = build_dashboard_conditions(filters)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = f"""
            SELECT s.enrollment_no, s.name, s.department, s.semester, 
                   sub.subject_name, m.total_marks, m.status
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            ORDER BY s.enrollment_no
        """
        cursor.execute(query, values)
        data = cursor.fetchall()
        conn.close()
        
        if not data: return None
        
        df = pd.DataFrame(data)
        file_name = f"analytical_report_{date.today().strftime('%Y%m%d')}.csv"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        df.to_csv(file_path, index=False)
        return file_path
    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return None

def export_report_pdf(filters={}, data={}):
    """Generate a comprehensive multi-chart PDF summary of the filtered academic landscape"""
    try:
        from fpdf import FPDF
        from datetime import date
        
        class PDF(FPDF):
            def header(self):
                self.set_fill_color(99, 102, 241)
                self.rect(0, 0, 210, 40, 'F')
                self.set_y(10)
                self.set_font('Helvetica', 'B', 24)
                self.set_text_color(255, 255, 255)
                self.cell(0, 10, ' SPDA ANALYTICAL INSIGHTS ', ln=True, align='C')
                self.set_font('Helvetica', 'I', 10)
                self.cell(0, 5, f'Generated: {date.today().strftime("%d %B, %Y")} | Academic Intelligence Unit', ln=True, align='C')
                self.ln(20)

        pdf = PDF()
        pdf.add_page()
        
        # 1. Executive Summary
        pdf.ln(15)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 10, '1. Filter Parameters & Scope', ln=True)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 7, f"Department Focus: {filters.get('department') or 'Institutional Wide'}", ln=True)
        pdf.cell(0, 7, f"Semester Layer: {filters.get('semester') or 'All Semesters'}", ln=True)
        pdf.cell(0, 7, f"Subject Focus: {filters.get('subject') or 'Global Curriculum'}", ln=True)
        pdf.ln(10)

        # 2. Key Charting Insights
        chart_files = [
            ('Performance Benchmarking by Department', 'report_dept.png'),
            ('Academic Growth Curve across Semesters', 'report_sem.png'),
            ('Critical Subject Strength Distribution', 'report_sub.png')
        ]
        
        for title, img in chart_files:
            img_path = os.path.join(CHARTS_DIR, img)
            if os.path.exists(img_path):
                pdf.set_font('Helvetica', 'B', 14)
                pdf.cell(0, 10, title, ln=True)
                pdf.image(img_path, x=15, w=180)
                pdf.ln(15)
                
                # Manual Page Breaks for better layout
                if title != 'Critical Subject Strength Distribution':
                    pdf.add_page()

        # Final Outcome Summary
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'Final Success & Engagement Distribution', ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10)
        
        if os.path.exists(os.path.join(CHARTS_DIR, 'report_pf.png')):
            pdf.image(os.path.join(CHARTS_DIR, 'report_pf.png'), x=10, w=90)
        if os.path.exists(os.path.join(CHARTS_DIR, 'report_att.png')):
            pdf.image(os.path.join(CHARTS_DIR, 'report_att.png'), x=110, y=pdf.get_y()-90, w=90)

        file_path = os.path.join(UPLOADS_DIR, f"Institutional_Report_{date.today().strftime('%Y%m%d')}.pdf")
        pdf.output(file_path)
        return file_path
    except Exception as e:
        print(f"Error exporting PDF report: {e}")
        return None

def get_faculty_analytics(filters={}):
    """Aggregate teacher-level performance metrics based on student outcomes"""
    conn = get_db_connection()
    if not conn: return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT f.faculty_id, f.faculty_name, f.department, f.email,
                   GROUP_CONCAT(DISTINCT sub.subject_name SEPARATOR ', ') as subjects_taught,
                   AVG(m.total_marks) as avg_marks,
                   COALESCE(COUNT(CASE WHEN m.total_marks >= 40 THEN 1 END)*100.0 / NULLIF(COUNT(m.id), 0), 0) as pass_percentage,
                   COUNT(DISTINCT m.enrollment_no) as total_students
            FROM faculty f
            JOIN subjects sub ON f.faculty_id = sub.faculty_id
            LEFT JOIN marks m ON sub.subject_id = m.subject_id
            WHERE 1=1
        """
        params = []
        if filters.get('department') and filters['department'] != 'All':
            query += " AND f.department = %s"
            params.append(filters['department'])
            
        query += " GROUP BY f.faculty_id ORDER BY avg_marks DESC"
        cursor.execute(query, params)
        analytics = cursor.fetchall()
        
        for record in analytics:
            avg = float(record['avg_marks'] or 0)
            if avg > 75: record['status'] = 'Excellent'
            elif avg >= 50: record['status'] = 'Average'
            else: record['status'] = 'Needs Improvement'
            
        return analytics
    except Exception as e:
        print(f"Error in faculty analytics calculation: {e}")
        return []
    finally:
        conn.close()

def generate_faculty_performance_charts(analytics):
    """Generate comparative charts for faculty benchmarking"""
    try:
        if not analytics: return
        plt.style.use('ggplot')
        
        names = [f['faculty_name'][:12] + '..' if len(f['faculty_name']) > 12 else f['faculty_name'] for f in analytics]
        avg_marks = [float(f['avg_marks'] or 0) for f in analytics]
        
        plt.figure(figsize=(12, 6))
        colors = ['#10b981' if x > 75 else '#6366f1' if x >= 50 else '#ef4444' for x in avg_marks]
        
        plt.bar(names, avg_marks, color=colors, alpha=0.85, edgecolor='#334155', linewidth=1)
        plt.axhline(y=50, color='#94a3b8', linestyle='--', alpha=0.5, label='Benchmark (50%)')
        plt.title('Faculty Performance Index (Student Success Rate)', fontsize=14, fontweight='bold', pad=20)
        plt.ylabel('Average Performance (%)', fontweight='bold')
        plt.ylim(0, 100)
        plt.xticks(rotation=15, fontsize=9)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, 'faculty_benchmarking.png'), dpi=200)
        plt.close()
    except Exception as e:
        print(f"Faculty chart error: {e}")

def get_single_faculty_detail(faculty_id):
    """Deep dive into a specific faculty's teaching metrics and trends"""
    conn = get_db_connection()
    if not conn: return None
    
    try:
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
        
        if not profile: return None
        
        # Subject-wise breakdown
        cursor.execute("""
            SELECT sub.subject_name, sub.semester,
                   AVG(m.total_marks) as avg_marks,
                   COALESCE(COUNT(CASE WHEN m.total_marks >= 40 THEN 1 END)*100.0 / NULLIF(COUNT(m.id), 0), 0) as pass_pct,
                   COUNT(m.id) as entry_count
            FROM subjects sub
            LEFT JOIN marks m ON sub.subject_id = m.subject_id
            WHERE sub.faculty_id = %s
            GROUP BY sub.subject_id
        """, (faculty_id,))
        subjects = cursor.fetchall()
        
        return {'profile': profile, 'subjects': subjects}
    except Exception as e:
        print(f"Error in single faculty detail: {e}")
        return None
    finally:
        conn.close()
