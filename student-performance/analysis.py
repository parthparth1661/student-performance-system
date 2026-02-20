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

def get_dashboard_stats(department=None, semester=None, exam_type=None):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Base filters for students and marks
        student_where = "WHERE 1=1"
        marks_where = "WHERE 1=1"
        params = []
        
        if department and department != 'All':
            student_where += " AND department = %s"
            marks_where += " AND s.department = %s"
            params.append(department)
        
        if semester and semester != 'All':
            student_where += " AND semester = %s"
            marks_where += " AND s.semester = %s"
            params.append(semester)
            
        marks_params = list(params)
        if exam_type and exam_type != 'All':
            # This applies to the marks table specifically
            marks_where += " AND m.exam_type = %s"
            marks_params.append(exam_type)

        # 1. Total Students (Filtered by Dept/Sem)
        cursor.execute(f"SELECT COUNT(*) as count FROM students {student_where}", params)
        total_students = cursor.fetchone()['count']
        
        # 1.b Total Departments (New)
        cursor.execute("SELECT COUNT(DISTINCT department) as count FROM students")
        total_depts = cursor.fetchone()['count']
        
        # 2. Total Marks Records (Filtered by All)
        cursor.execute(f"""
            SELECT COUNT(*) as count 
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            {marks_where}
        """, marks_params)
        total_marks = cursor.fetchone()['count']
        
        # 3. Subject-wise average marks
        cursor.execute(f"""
            SELECT m.subject, AVG(m.marks) as avg_marks 
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            {marks_where}
            GROUP BY m.subject
        """, marks_params)
        subject_avg = cursor.fetchall()
        
        # Filter subjects based on department if selected
        if department and department in DEPARTMENT_SUBJECTS:
            allowed = DEPARTMENT_SUBJECTS[department]
            subject_avg = [s for s in subject_avg if s['subject'] in allowed]
        
        # 4. Overall Pass % (Passing all subjects >= 35)
        # Calculate distinct students who failed at least one subject
        cursor.execute(f"""
            SELECT COUNT(DISTINCT m.student_id) as fail_count
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            {marks_where} AND m.marks < 35
        """, marks_params)
        students_failed_at_least_one = cursor.fetchone()['fail_count']
        
        pass_count = total_students - students_failed_at_least_one
        pass_percent = (pass_count / total_students * 100) if total_students > 0 else 0
        
        # 4b. Pie Chart Pass/Fail (Subject-wise records)
        cursor.execute(f"""
            SELECT 
                SUM(CASE WHEN m.marks >= 35 THEN 1 ELSE 0 END) as pass_count,
                SUM(CASE WHEN m.marks < 35 THEN 1 ELSE 0 END) as fail_count
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            {marks_where}
        """, marks_params)
        res = cursor.fetchone()
        rec_pass = res['pass_count'] if res['pass_count'] else 0
        rec_fail = res['fail_count'] if res['fail_count'] else 0
        
        # 5. Top/Weak students
        cursor.execute(f"""
            SELECT s.roll_no, s.name, AVG(m.marks) as avg_marks
            FROM students s
            JOIN marks m ON s.student_id = m.student_id
            {marks_where}
            GROUP BY s.student_id, s.roll_no, s.name
            ORDER BY avg_marks DESC
            LIMIT 5
        """, marks_params)
        top_students = cursor.fetchall()
        
        cursor.execute(f"""
            SELECT s.roll_no, s.name, AVG(m.marks) as avg_marks
            FROM students s
            JOIN marks m ON s.student_id = m.student_id
            {marks_where}
            GROUP BY s.student_id, s.roll_no, s.name
            ORDER BY avg_marks ASC
            LIMIT 5
        """, marks_params)
        weak_students = cursor.fetchall()

        # 6. Marks Distribution (for Histogram)
        cursor.execute(f"""
            SELECT m.marks 
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
            {marks_where}
        """, marks_params)
        all_marks = [row['marks'] for row in cursor.fetchall()]

        # 7. Attendance Stats
        cursor.execute("SELECT COUNT(*) as total_days FROM (SELECT DISTINCT attendance_date FROM attendance) as dates")
        total_days = cursor.fetchone()['total_days'] or 0
        
        cursor.execute("SELECT COUNT(*) as count FROM attendance WHERE status = 'Present'")
        total_present = cursor.fetchone()['count'] or 0
        
        cursor.execute("SELECT COUNT(*) as count FROM attendance")
        total_marked = cursor.fetchone()['count'] or 0
        
        avg_attendance = (total_present / total_marked * 100) if total_marked > 0 else 0
        
        # Low attendance count (< 75%)
        att_summary = get_attendance_summary()
        low_att_count = len([s for s in att_summary if s['percentage'] < 75]) if att_summary else 0

        cursor.close()
        conn.close()
        
        # Generate HD Charts
        generate_subject_avg_chart(subject_avg)
        generate_pass_fail_pie({'pass_count': rec_pass, 'fail_count': rec_fail}) # Pie uses subject records
        generate_marks_distribution(all_marks)
        
        return {
            'total_students': total_students,
            'total_departments': total_depts,
            'pass_percentage': round(pass_percent, 1),
            'total_marks': total_marks,
            'pass_count': int(rec_pass),
            'fail_count': int(rec_fail),
            'subject_avg': subject_avg,
            'top_students': top_students,
            'weak_students': weak_students,
            'avg_attendance': round(avg_attendance, 2),
            'low_att_count': low_att_count
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
        
        # Modern color palette (Blue-Indigo)
        bars = plt.bar(subjects, averages, color='#4F46E5', edgecolor='#3730A3', alpha=0.85, width=0.6)
        
        # Add values on top of bars
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
        # Modern colors: Emerald for Pass, Rose for Fail
        colors = ['#10B981', '#F43F5E']
        
        # Create pie chart with clean aesthetics
        wedges, texts, autotexts = plt.pie(
            sizes, labels=labels, colors=colors, autopct='%1.1f%%', 
            startangle=140, pctdistance=0.85, 
            wedgeprops={'linewidth': 3, 'edgecolor': 'white', 'antialiased': True}
        )
        
        # Style text labels
        for t in texts:
            t.set_fontsize(12)
            t.set_fontweight('bold')
        for at in autotexts:
            at.set_fontsize(11)
            at.set_fontweight('bold')
            at.set_color('white')
            
        # Add a light donut hole for modern look (Optional, but looks premium)
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
    else:
        plt.text(0, 0, 'No Data Available', ha='center', va='center', fontsize=14)
        
    plt.title('Pass/Fail Distribution (By Subject Records)', fontsize=16, fontweight='bold', pad=25)
    plt.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
    
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_DIR, 'admin_pass_fail.png'), bbox_inches="tight")
    plt.close()

def generate_marks_distribution(all_marks):
    """Generates an HD Marks Distribution Histogram"""
    plt.figure(figsize=(12, 6), dpi=200)
    
    if all_marks:
        # Modern color: Violet
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

# ... (imports)

def get_working_days(department, semester):
    """Calculates total working days for a specific term, excluding Sundays and Holidays."""
    conn = get_db_connection()
    if not conn: return 0
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Get Term Dates
        cursor.execute("""
            SELECT start_date, end_date FROM academic_calendar 
            WHERE department = %s AND semester = %s
        """, (department, semester))
        term = cursor.fetchone()
        
        if not term:
            return 0 # Term not defined
            
        start_date = term['start_date']
        end_date = term['end_date']
        
        # 2. Get Holidays within range
        cursor.execute("""
            SELECT holiday_date FROM holidays 
            WHERE holiday_date BETWEEN %s AND %s
        """, (start_date, end_date))
        holidays = {row['holiday_date'] for row in cursor.fetchall()}
        
        # 3. Calculate Working Days
        total_days = (end_date - start_date).days + 1
        working_days = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Check if Sunday (6) or Holiday
            if current_date.weekday() != 6 and current_date not in holidays:
                working_days += 1
            current_date += timedelta(days=1)
            
        cursor.close()
        conn.close()
        return working_days
        
    except Exception as e:
        print(f"Error calculating working days: {e}")
        return 0

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
        
        # 1. STUDENTS CSV: roll_no, name, email, department, semester
        if all(x in cols for x in ['roll_no', 'name', 'email', 'department', 'semester']):
            from werkzeug.security import generate_password_hash
            
            for idx, row in df.iterrows():
                try:
                    default_pw = str(row['roll_no']) + "@123"
                    pw_hash = generate_password_hash(default_pw)
                    
                    cursor.execute("""
                        INSERT INTO students (roll_no, name, email, department, semester, password_hash, is_password_changed)
                        VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email), department=VALUES(department), semester=VALUES(semester)
                    """, (row['roll_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Student"

        # 2. MARKS CSV: roll_no, subject, marks, exam_type, exam_date
        elif all(x in cols for x in ['roll_no', 'subject', 'marks', 'exam_type', 'exam_date']):
            valid_types = ['Internal', 'External', 'Practical']
            for idx, row in df.iterrows():
                try:
                    if row['exam_type'] not in valid_types:
                        errors.append(f"Row {idx+2}: Invalid exam_type '{row['exam_type']}'")
                        continue
                        
                    # Get student_id
                    cursor.execute("SELECT student_id, department FROM students WHERE roll_no = %s", (row['roll_no'],))
                    student = cursor.fetchone()
                    
                    if not student:
                        errors.append(f"Row {idx+2}: Student {row['roll_no']} not found")
                        continue
                        
                    # MBA rule
                    if row['exam_type'] == 'Practical' and student[1] == 'MBA':
                         errors.append(f"Row {idx+2}: MBA cannot have Practical marks")
                         continue

                    cursor.execute("""
                        INSERT INTO marks (student_id, subject, marks, exam_type, exam_date)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (student[0], row['subject'], row['marks'], row['exam_type'], row['exam_date']))
                    success_count += 1
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Marks"

        # 3. ATTENDANCE CSV: roll_no, attendance_date, status, remarks
        elif all(x in cols for x in ['roll_no', 'attendance_date', 'status', 'remarks']):
            
            # Pre-fetch term dates/holidays if validating strictly
            term_start = None
            term_end = None
            holidays = set()
            
            if department and semester:
                cursor.execute("SELECT start_date, end_date FROM academic_calendar WHERE department=%s AND semester=%s", (department, semester))
                term = cursor.fetchone()
                if term:
                    term_start = term[0]
                    term_end = term[1]
                    
                cursor.execute("SELECT holiday_date FROM holidays")
                holidays = {row[0] for row in cursor.fetchall()}

            for idx, row in df.iterrows():
                try:
                    # Validate Date Logic
                    att_date_str = row['attendance_date']
                    att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date()
                    
                    if term_start and term_end:
                         if not (term_start <= att_date <= term_end):
                             errors.append(f"Row {idx+2}: Date {att_date} outside academic term")
                             continue
                             
                    if att_date.weekday() == 6:
                        errors.append(f"Row {idx+2}: Cannot mark attendance on Sunday ({att_date})")
                        continue
                        
                    if att_date in holidays:
                        errors.append(f"Row {idx+2}: Cannot mark attendance on Holiday ({att_date})")
                        continue

                    # Fetch Student
                    cursor.execute("SELECT student_id, department, semester FROM students WHERE roll_no = %s", (row['roll_no'],))
                    student = cursor.fetchone()
                    
                    if not student:
                         errors.append(f"Row {idx+2}: Student {row['roll_no']} not found")
                         continue
                    
                    # Validate Dept/Sem match if provided
                    # Ensure robust string comparison
                    stu_dept = str(student[1]).strip() if student[1] else ''
                    stu_sem = str(student[2]).strip() if student[2] else ''
                    req_dept = str(department).strip() if department else ''
                    req_sem = str(semester).strip() if semester else ''
                    
                    if req_dept and stu_dept != req_dept:
                        errors.append(f"Row {idx+2}: Student belongs to {stu_dept}, not {req_dept}")
                        continue
                        
                    if req_sem and stu_sem != req_sem:
                        errors.append(f"Row {idx+2}: Student is in {stu_sem}, not {req_sem}")
                        continue

                    cursor.execute("""
                        INSERT INTO attendance (student_id, attendance_date, status, remarks)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE status=VALUES(status), remarks=VALUES(remarks)
                    """, (student[0], row['attendance_date'], row['status'], row['remarks']))
                    success_count += 1
                except ValueError:
                    errors.append(f"Row {idx+2}: Invalid date format. Use YYYY-MM-DD")
                except Exception as e:
                    errors.append(f"Row {idx+2}: {str(e)}")
            msg_type = "Attendance"
            
        else:
            return False, "Unknown CSV format. Please check headers."

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
    """Fetches student profile details using enrollment number (roll_no)"""
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE roll_no = %s", (enrollment_no,))
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
        # Get student_id first
        cursor.execute("SELECT student_id, department FROM students WHERE roll_no = %s", (enrollment_no,))
        student = cursor.fetchone()
        if not student:
            conn.close()
            return []
        
        student_id = student['student_id']
        dept = student['department']

        # Fetch all marks for this student
        cursor.execute("SELECT * FROM marks WHERE student_id = %s", (student_id,))
        marks_records = cursor.fetchall()
        cursor.close()
        conn.close()

        if not marks_records:
            return []

        df = pd.DataFrame(marks_records)
        
        # Pivot the data to get Internal, External, Practical in columns per subject
        subjects_data = []
        for subject in df['subject'].unique():
            subj_df = df[df['subject'] == subject]
            
            internal = subj_df[subj_df['exam_type'] == 'Internal']['marks'].sum()
            external = subj_df[subj_df['exam_type'] == 'External']['marks'].sum()
            # If no external marks record exists, we might need a default or handled case
            # But usually they'll be there if any marks exist.
            
            practical = 0
            if dept == 'MBA':
                p_display = "N/A"
            else:
                practical = subj_df[subj_df['exam_type'] == 'Practical']['marks'].sum()
                p_display = int(practical)

            total = internal + external + practical
            
            # Status: PASS if External >= 35, else FAIL
            # Checking if External record exists to avoid false PASS on missing record
            has_external = not subj_df[subj_df['exam_type'] == 'External'].empty
            status = "PASS" if (has_external and external >= 35) else "FAIL"
            
            # Suggestion logic
            suggestion = ""
            if external < 35 or total < 120:
                if 'DBMS' in subject.upper():
                    suggestion = "Focus more on DBMS fundamentals"
                elif 'DSA' in subject.upper() or 'DATA STRUCTURE' in subject.upper():
                    suggestion = "Revise DSA problem solving"
                elif 'PYTHON' in subject.upper():
                    suggestion = "Practice more Python coding"
                else:
                    suggestion = f"Need more effort in {subject}"

            subjects_data.append({
                'subject': subject,
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
    """Calculates student-wise attendance percentage and stats based on GTU Working Days"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                s.roll_no, 
                s.name, 
                s.department, 
                s.semester,
                COUNT(a.attendance_id) as marked_days,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            GROUP BY s.student_id
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
    """Returns students who failed any subject in external exams (marks < threshold)"""
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.roll_no, s.name, s.department, s.semester, COUNT(m.marks_id) as fail_count
            FROM students s
            JOIN marks m ON s.student_id = m.student_id
            WHERE m.exam_type = 'External' AND m.marks < %s
            GROUP BY s.student_id
            ORDER BY fail_count DESC
        """, (threshold,))
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
        query_s = "SELECT student_id, roll_no, name, email, department, semester FROM students WHERE 1=1"
        params_s = []
        if department != 'All':
            query_s += " AND department = %s"
            params_s.append(department)
        if semester != 'All':
            query_s += " AND semester = %s"
            params_s.append(semester)
        
        df_students = pd.read_sql(query_s, conn, params=params_s)
        
        # 2. Marks Sheet (Joined)
        query_m = """
            SELECT s.roll_no, s.name, m.subject, m.marks, m.exam_type, m.exam_date
            FROM marks m
            JOIN students s ON m.student_id = s.student_id
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
        
        # 3. Attendance Sheet (Joined)
        query_a = """
            SELECT s.roll_no, s.name, a.attendance_date, a.status, a.remarks
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
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
