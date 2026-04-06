import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import os
from db import get_db_connection

# Ensure charts directory exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARTS_DIR = os.path.join(BASE_DIR, 'static', 'charts')
if not os.path.exists(CHARTS_DIR):
    os.makedirs(CHARTS_DIR)

DEPARTMENT_SUBJECTS = {
    'BCA': ['Python Programming', 'Java Programming', 'DBMS', 'Data Structures', 'Operating Systems', 'Web Technology'],
    'MCA': ['Advanced Python', 'Java', 'DBMS', 'DSA', 'Computer Networks', 'Software Engineering'],
    'B.TECH': ['Engineering Mathematics', 'Data Structures', 'DBMS', 'Operating Systems', 'Computer Networks', 'Software Engineering'],
    'M.TECH': ['Advanced Algorithms', 'Machine Learning', 'Cloud Computing', 'Distributed Systems', 'Data Mining', 'Research Methodology'],
    'MBA': ['Marketing Management', 'Financial Management', 'Human Resource Management', 'Operations Management', 'Business Analytics', 'Strategic Management']
}

def get_dashboard_stats(filters={}):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 0. Shared Filtering Logic
        core_where = []
        core_vals = []
        if filters.get('department'):
            core_where.append("s.department = %s")
            core_vals.append(filters['department'])
        if filters.get('semester'):
            core_where.append("s.semester = %s")
            core_vals.append(filters['semester'])
        
        where_clause = " WHERE " + " AND ".join(core_where) if core_where else ""

        # 1. Total Students
        cursor.execute(f"SELECT COUNT(*) as count FROM students s {where_clause}", core_vals)
        total_students = cursor.fetchone()['count']
        
        # 2. Total Faculty (Faculty are usually global, but let's filter if requested)
        cursor.execute("SELECT COUNT(*) as count FROM faculty")
        total_faculty = cursor.fetchone()['count']
        
        # 3. Total Subjects
        sub_where = " WHERE " + " AND ".join(core_where).replace('s.', '') if core_where else ""
        sub_vals = [v for v in core_vals]
        cursor.execute(f"SELECT COUNT(*) as count FROM subjects {sub_where}", sub_vals)
        total_subjects = cursor.fetchone()['count']
        
        # 4. Total Marks Records
        cursor.execute(f"""
            SELECT COUNT(*) as count 
            FROM marks m 
            JOIN students s ON m.enrollment_no = s.enrollment_no 
            {where_clause}
        """, core_vals)
        total_marks = cursor.fetchone()['count']
        
        # 5. Pass/Fail Counts
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN marks_obtained >= (total_marks * 0.35) THEN 1 ELSE 0 END) as pass_count,
                SUM(CASE WHEN marks_obtained < (total_marks * 0.35) THEN 1 ELSE 0 END) as fail_count
            FROM marks
        """)
        res = cursor.fetchone()
        pass_count = res['pass_count'] or 0
        fail_count = res['fail_count'] or 0
        
        # 6. Top Students
        cursor.execute("""
            SELECT s.enrollment_no as roll_no, s.name, AVG(m.marks_obtained) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            GROUP BY s.enrollment_no, s.name
            ORDER BY avg_marks DESC
            LIMIT 5
        """)
        top_students = cursor.fetchall()
        
        # 7. Attendance stats
        cursor.execute("SELECT COUNT(*) as count FROM attendance WHERE status = 'Present'")
        present = cursor.fetchone()['count'] or 0
        cursor.execute("SELECT COUNT(*) as count FROM attendance")
        total_att = cursor.fetchone()['count'] or 0
        avg_attendance = (present / total_att * 100) if total_att > 0 else 0

        # 8. Chart Data
        cursor.execute("""
            SELECT sub.subject_name as subject, AVG(m.marks_obtained) as avg_marks
            FROM marks m
            JOIN subjects sub ON m.subject_id = sub.subject_id
            GROUP BY m.subject_id
        """)
        subject_avg_data = cursor.fetchall()

        cursor.execute("SELECT marks_obtained FROM marks")
        all_marks_raw = cursor.fetchall()
        all_marks = [row['marks_obtained'] for row in all_marks_raw]

        # 9. NEW CORE METRICS (STEP 1) 🎯
        cursor.execute(f"""
            SELECT AVG(m.marks_obtained) AS avg_marks 
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            {where_clause}
        """, core_vals)
        avg_marks = cursor.fetchone()['avg_marks'] or 0
        
        cursor.execute(f"""
            SELECT (COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) 
            AS attendance_percentage 
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            {where_clause}
        """, core_vals)
        attendance_percentage = cursor.fetchone()['attendance_percentage'] or 0

        # 📊 --- NEW MATPLOTLIB ANALYTICS (STEP 3 & 4) ---
        import matplotlib.pyplot as plt
        import os

        # --- BAR CHART: AVG MARKS (STEP 3) ---
        bar_query = f"""
            SELECT sub.subject_name, AVG(m.marks_obtained) as avg_marks
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            {where_clause}
            GROUP BY sub.subject_name
        """
        cursor.execute(bar_query, core_vals)
        bar_data = cursor.fetchall()
        
        if bar_data:
            subjects = [row['subject_name'] for row in bar_data]
            marks = [float(row['avg_marks']) for row in bar_data]
            plt.figure(figsize=(6,4))
            plt.bar(subjects, marks, color='purple')
            plt.title("Average Marks per Subject")
            plt.xlabel("Subjects")
            plt.ylabel("Marks")
            plt.tight_layout()
            plt.savefig("static/bar_chart.png")
            plt.close()

        # --- PIE CHART: ATTENDANCE (STEP 4) ---
        pie_query = f"""
            SELECT a.status, COUNT(*) as count
            FROM attendance a
            JOIN students s ON a.enrollment_no = s.enrollment_no
            {where_clause}
            GROUP BY a.status
        """
        cursor.execute(pie_query, core_vals)
        pie_data = cursor.fetchall()
        
        if pie_data:
            labels = [row['status'] for row in pie_data]
            counts = [row['count'] for row in pie_data]
            plt.figure(figsize=(5,5))
            plt.pie(counts, labels=labels, autopct='%1.1f%%', colors=['#4f46e5', '#f59e0b', '#ef4444'])
            plt.title("Attendance Distribution")
            plt.savefig("static/pie_chart.png")
            plt.close()

        cursor.close()
        conn.close()
        
        return {
            'total_students': total_students,
            'total_faculty': total_faculty,
            'total_subjects': total_subjects,
            'total_marks': total_marks,
            'avg_marks': round(avg_marks, 2),
            'attendance_percentage': round(attendance_percentage, 2),
            'top_students': top_students
        }
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return None

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
        cols = [c.strip().lower() for c in df.columns]
        df.columns = cols # Normalize headers
        
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
    """Generates charts specifically for the student dashboard"""
    subjects_data = get_student_marks(enrollment_no)
    if not subjects_data:
        return
    
    # Chart 1: Subject-wise Total Marks (Bar)
    plt.figure(figsize=(12, 6), dpi=200)
    subjects = [item['subject'] for item in subjects_data]
    totals = [item['total'] for item in subjects_data]
    
    colors = ['#3B82F6', '#6366F1', '#8B5CF6', '#EC4899', '#10B981', '#F59E0B'] # Vibrant palette
    plt.bar(subjects, totals, color=colors[:len(subjects)], alpha=0.9, edgecolor='white', linewidth=1)
    
    plt.title(f'Subject-wise Total Performance', fontsize=16, fontweight='bold', pad=25)
    plt.xlabel('Subjects', fontsize=12)
    plt.ylabel('Total Marks', fontsize=12)
    plt.xticks(rotation=20, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.tight_layout()
    
    bar_path = os.path.join(CHARTS_DIR, f'student_{enrollment_no}_bar.png')
    plt.savefig(bar_path, bbox_inches="tight")
    plt.close()

    # Chart 2: Pass vs Fail Subjects (Pie)
    pass_count = sum(1 for item in subjects_data if item['status'] == "PASS")
    fail_count = sum(1 for item in subjects_data if item['status'] == "FAIL")
    
    plt.figure(figsize=(12, 6), dpi=200)
    if pass_count + fail_count > 0:
        plt.pie([pass_count, fail_count], labels=['Pass', 'Fail'], 
                colors=['#10B981', '#EF4444'], autopct='%1.1f%%', 
                startangle=140, wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    else:
        plt.text(0.5, 0.5, 'No Data', ha='center', va='center')
        
    plt.title('Pass vs Fail Subjects', fontsize=16, fontweight='bold', pad=25)
    plt.tight_layout()
    
    pie_path = os.path.join(CHARTS_DIR, f'student_{enrollment_no}_pie.png')
    plt.savefig(pie_path, bbox_inches="tight")
    plt.close()

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
def get_performance_overview(department=None, semester=None):
    """Dynamic query for performance overview with filters"""
    conn = get_db_connection()
    if not conn: return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Use attendance_id for COUNT
        query = """
            SELECT 
                s.name,
                sub.subject_name,
                AVG(m.marks_obtained) AS avg_marks,
                (COUNT(CASE WHEN a.status='Present' THEN 1 END)*100.0/NULLIF(COUNT(a.attendance_id), 0)) AS attendance_percentage
            FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
            JOIN attendance a 
                ON s.enrollment_no = a.enrollment_no 
                AND sub.subject_id = a.subject_id
        """
        
        conditions = []
        values = []
        
        if department and department != 'All':
            conditions.append("s.department = %s")
            values.append(department)
            
        if semester and semester != 'All':
            conditions.append("s.semester = %s")
            values.append(semester)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " GROUP BY s.name, sub.subject_name"
        
        cursor.execute(query, values)
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except Exception as e:
        print(f"Error in performance overview: {e}")
        return []

def export_admin_excel(department='All', semester='All'):
    """Exports filtered performance overview to Excel"""
    try:
        import pandas as pd
        data = get_performance_overview(department, semester)
        if not data: return None
        
        df = pd.DataFrame(data)
        file_name = f"performance_report_{department}_{semester}.xlsx"
        file_path = os.path.join(UPLOADS_DIR, file_name)
        
        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)
            
        df.to_excel(file_path, index=False)
        return file_path
    except Exception as e:
        print(f"Error exporting admin excel: {e}")
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
