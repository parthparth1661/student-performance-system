from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from datetime import date
import os

admin_bp = Blueprint('admin', __name__)

# --- Authentication Protection ---
@admin_bp.before_request
def check_admin_login():
    if request.endpoint in ['admin.login', 'admin.logout', 'admin.static']: 
        return
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email') or request.form.get('username') # Handle both for compatibility
        password = request.form.get('password')
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('admin/admin_login.html')
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
            admin = cursor.fetchone()
            if admin and check_password_hash(admin['password'], password):
                session['admin_logged_in'] = True
                session['admin_email'] = admin['email']
                flash(f"Welcome back, Administrator!", "success")
                return redirect(url_for('admin.dashboard'))
            else:
                flash("Invalid email or password.", "danger")
        except Exception as e:
            flash(f"Login error: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template('admin/admin_login.html')

@admin_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('admin.login'))

@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    # 🎯 🧠 STEP 1: GET FILTER VALUES (DISCOVERY)
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'attendance': request.args.get('attendance'),
        'subject': request.args.get('subject')
    }

    # 🧱 🧬 STEP 2: BUILD DYNAMIC CONDITIONS (MULTI-LEVEL)
    conditions = []
    values = []
    
    if filters['department']:
        conditions.append("s.department = %s")
        values.append(filters['department'])
    if filters['semester']:
        conditions.append("s.semester = %s")
        values.append(filters['semester'])
    if filters.get('subject'):
        conditions.append("su.subject_name = %s")
        values.append(filters['subject'])
    if filters['search']:
        search_query = f"%{filters['search']}%"
        conditions.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
        values.append(search_query)
        values.append(search_query)
    
    # --- 🛰️ STEP 3: ATTENDANCE AUDIT LOGIC (SUBQUERY) ---
    if filters['attendance'] == "low":
        conditions.append("""
            s.enrollment_no IN (
                SELECT enrollment_no FROM attendance 
                GROUP BY enrollment_no 
                HAVING (COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / COUNT(*)) < 75
            )
        """)
    elif filters['attendance'] == "high":
        conditions.append("""
            s.enrollment_no IN (
                SELECT enrollment_no FROM attendance 
                GROUP BY enrollment_no 
                HAVING (COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / COUNT(*)) >= 75
            )
        """)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    stats = {}
    performance_overview = []
    all_subjects = []

    try:
        # Fetch all subjects for the filter dropdown
        cursor.execute("SELECT DISTINCT subject_name FROM subjects ORDER BY subject_name ASC")
        all_subjects = [r['subject_name'] for r in cursor.fetchall()]

        # --- Apply Conditions to KPI Suite ---
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # 📊 1. Total Students
        cursor.execute("SELECT COUNT(*) AS total FROM students s" + where_clause, values)
        stats['total_students'] = cursor.fetchone()['total']

        # 📊 2. Total Subjects (Respecting Dept/Sem filters)
        sub_conditions = []
        sub_values = []
        if filters['department']:
            sub_conditions.append("department = %s")
            sub_values.append(filters['department'])
        if filters['semester']:
            sub_conditions.append("semester = %s")
            sub_values.append(filters['semester'])
        
        sub_where = " WHERE " + " AND ".join(sub_conditions) if sub_conditions else ""
        cursor.execute("SELECT COUNT(*) AS total FROM subjects" + sub_where, sub_values)
        stats['total_subjects'] = cursor.fetchone()['total']

        # 📊 3. Average Marks
        query = """SELECT AVG(m.marks_obtained) AS avg FROM marks m
                   JOIN students s ON m.enrollment_no = s.enrollment_no
                   LEFT JOIN subjects su ON m.subject_id = su.subject_id"""
        cursor.execute(query + where_clause, values)
        res = cursor.fetchone()
        stats['avg_marks'] = round(res['avg'], 1) if res['avg'] else 0

        # 📊 4. Overall Attendance %
        query = """SELECT (COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / COUNT(*)) AS att 
                   FROM attendance a
                   JOIN students s ON a.enrollment_no = s.enrollment_no
                   LEFT JOIN subjects su ON a.subject_id = su.subject_id"""
        cursor.execute(query + where_clause, values)
        res = cursor.fetchone()
        stats['attendance_percentage'] = round(res['att'], 1) if res['att'] else 0

        # 📊 5. Low Attendance Count
        query_low = """
            SELECT COUNT(DISTINCT s.enrollment_no) as count FROM students s
            JOIN attendance a ON s.enrollment_no = a.enrollment_no
            LEFT JOIN subjects su ON a.subject_id = su.subject_id
            """ + where_clause + (" AND " if conditions else " WHERE ") + """
            s.enrollment_no IN (
                SELECT enrollment_no FROM attendance 
                GROUP BY enrollment_no 
                HAVING (COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / COUNT(*)) < 75
            )
        """
        cursor.execute(query_low, values)
        stats['low_attendance_count'] = cursor.fetchone()['count']

        # 📊 6. Top Performer
        query_top = """
            SELECT s.name, AVG(m.marks_obtained) as avg_m FROM students s
            JOIN marks m ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects su ON m.subject_id = su.subject_id
            """ + where_clause + """
            GROUP BY s.enrollment_no, s.name
            ORDER BY avg_m DESC LIMIT 1
        """
        cursor.execute(query_top, values)
        res_top = cursor.fetchone()
        stats['top_performer'] = res_top['name'] if res_top else "N/A"

        # 📊 Ledger Table (High-Fidelity JOINs)
        query_ledger = """
            SELECT s.enrollment_no, s.name, su.subject_name,
            AVG(m.marks_obtained) AS avg_marks,
            (COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / COUNT(*)) AS attendance_percentage
            FROM students s
            LEFT JOIN marks m ON s.enrollment_no = m.enrollment_no
            LEFT JOIN subjects su ON m.subject_id = su.subject_id
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
        """
        if conditions: query_ledger += " WHERE " + " AND ".join(conditions)
        query_ledger += " GROUP BY s.enrollment_no, s.name, su.subject_name ORDER BY s.name ASC"
        cursor.execute(query_ledger, values)
        performance_overview = cursor.fetchall()

    except Exception as e:
        print(f"Discovery Engine Error: {str(e)}")
        stats = {'total_students': 0, 'avg_marks': 0, 'attendance_percentage': 0, 'total_subjects': 0, 'low_attendance_count': 0, 'top_performer': 'N/A'}
    finally:
        cursor.close()
        conn.close()

    return render_template('admin/admin_dashboard.html', 
                         stats=stats, 
                         filters=filters, 
                         performance_overview=performance_overview,
                         subjects=all_subjects,
                         today_date=date.today().strftime('%d %b %Y'))

# --- 🧑🎓 1. STUDENTS MODULE ---
@admin_bp.route('/students')
def view_students():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    conn.close()
    return render_template('admin/view_students.html', students=students)

@admin_bp.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            pw_hash = generate_password_hash(enrollment_no + "@123")
            cursor.execute("""
                INSERT INTO students (enrollment_no, name, email, department, semester, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (enrollment_no, name, email, department, semester, pw_hash))
            conn.commit()
            flash("Student added successfully!", "success")
            return redirect(url_for('admin.view_students'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()
    return render_template('admin/add_student.html')

# --- 📚 2. SUBJECTS MODULE ---
@admin_bp.route('/subjects')
def view_subjects():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, f.faculty_name 
        FROM subjects s 
        LEFT JOIN faculty f ON s.faculty_id = f.faculty_id
    """)
    subjects = cursor.fetchall()
    conn.close()
    return render_template('admin/view_subjects.html', subjects=subjects)

@admin_bp.route('/subjects/add', methods=['GET', 'POST'])
def add_subject():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM faculty")
    faculties = cursor.fetchall()
    
    if request.method == 'POST':
        subject_name = request.form['subject_name']
        department = request.form['department']
        semester = request.form['semester']
        faculty_id = request.form.get('faculty_id')
        
        try:
            cursor.execute("""
                INSERT INTO subjects (subject_name, department, semester, faculty_id)
                VALUES (%s, %s, %s, %s)
            """, (subject_name, department, semester, faculty_id))
            conn.commit()
            flash("Subject added successfully!", "success")
            return redirect(url_for('admin.view_subjects'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_subject.html', faculties=faculties)

# --- 👨🏫 3. FACULTY MODULE ---
@admin_bp.route('/faculty')
def view_faculty():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM faculty")
    faculties = cursor.fetchall()
    conn.close()
    return render_template('admin/view_faculty.html', faculties=faculties)

@admin_bp.route('/faculty/add', methods=['GET', 'POST'])
def add_faculty():
    if request.method == 'POST':
        faculty_name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO faculty (faculty_name, email, department)
                VALUES (%s, %s, %s)
            """, (faculty_name, email, department))
            conn.commit()
            flash("Faculty added successfully!", "success")
            return redirect(url_for('admin.view_faculty'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()
    return render_template('admin/add_faculty.html')

# --- 📊 4. MARKS MODULE ---
@admin_bp.route('/marks')
def view_marks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.*, s.name as student_name, sub.subject_name 
        FROM marks m
        JOIN students s ON m.enrollment_no = s.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
    """)
    marks_list = cursor.fetchall()
    conn.close()
    return render_template('admin/view_marks.html', marks_list=marks_list)

@admin_bp.route('/marks/add', methods=['GET', 'POST'])
def add_marks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        subject_id = request.form['subject_id']
        exam_type = request.form['exam_type']
        marks_obtained = request.form['marks_obtained']
        total_marks = request.form.get('total_marks', 100)
        
        try:
            cursor.execute("""
                INSERT INTO marks (enrollment_no, subject_id, exam_type, marks_obtained, total_marks)
                VALUES (%s, %s, %s, %s, %s)
            """, (enrollment_no, subject_id, exam_type, marks_obtained, total_marks))
            conn.commit()
            flash("Marks added successfully!", "success")
            return redirect(url_for('admin.view_marks'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_marks.html', students=students, subjects=subjects)

# --- 📅 5. ATTENDANCE MODULE ---
@admin_bp.route('/attendance')
def view_attendance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.*, s.name as student_name, sub.subject_name 
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        JOIN subjects sub ON a.subject_id = sub.subject_id
    """)
    records = cursor.fetchall()
    conn.close()
    return render_template('admin/view_attendance.html', records=records)

@admin_bp.route('/attendance/add', methods=['GET', 'POST'])
def add_attendance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        subject_id = request.form['subject_id']
        att_date = request.form['date']
        status = request.form['status']
        
        try:
            cursor.execute("""
                INSERT INTO attendance (enrollment_no, subject_id, date, status)
                VALUES (%s, %s, %s, %s)
            """, (enrollment_no, subject_id, att_date, status))
            conn.commit()
            flash("Attendance marked successfully!", "success")
            return redirect(url_for('admin.view_attendance'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_attendance.html', 
                          students=students, 
                          subjects=subjects, 
                          today_date=date.today().strftime('%Y-%m-%d'))
# --- DELETE & BULK ROUTES ---

@admin_bp.route('/students/delete/<enrollment_no>')
def delete_student(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE enrollment_no = %s", (enrollment_no,))
        conn.commit()
        flash("Student removed successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_students'))

@admin_bp.route('/faculty/delete/<int:faculty_id>')
def delete_faculty(faculty_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM faculty WHERE faculty_id = %s", (faculty_id,))
        conn.commit()
        flash("Faculty member removed.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_faculty'))

@admin_bp.route('/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        conn.commit()
        flash("Subject removed.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_subjects'))

@admin_bp.route('/marks/delete/<int:marks_id>')
def delete_marks(marks_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM marks WHERE marks_id = %s", (marks_id,))
        conn.commit()
        flash("Marks record deleted.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_marks'))

@admin_bp.route('/attendance/delete/<int:attendance_id>')
def delete_attendance(attendance_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM attendance WHERE attendance_id = %s", (attendance_id,))
        conn.commit()
        flash("Attendance record removed.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_attendance'))

@admin_bp.route('/bulk-upload', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash("No selected file", "danger")
            return redirect(request.url)

        if file and file.filename.endswith('.csv'):
            file_path = os.path.join('static', 'uploads', file.filename)
            if not os.path.exists('static/uploads'):
                os.makedirs('static/uploads')
            file.save(file_path)
            
            from analysis import process_csv
            success, message = process_csv(file_path)
            
            if success:
                flash(message, "success")
            else:
                flash(message, "danger")
        else:
            flash("Invalid file type. Please upload a CSV.", "warning")
            
    return render_template('admin/bulk_upload.html')

@admin_bp.route('/export-excel')
def export_excel():
    dept = request.args.get('department', 'All')
    sem = request.args.get('semester', 'All')
    sub = request.args.get('subject', 'All')
    search = request.args.get('search', None)
    att = request.args.get('attendance', None)
    
    from analysis import export_admin_excel
    file_path = export_admin_excel(dept, sem, sub, search, att)
    
    if file_path and os.path.exists(file_path):
        from flask import send_file
        return send_file(file_path, as_attachment=True)
    flash("Error generating report.", "danger")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/reset-data')
def reset_data():
    # Only reset dynamic data (not admin)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        tables = ['attendance', 'marks', 'subjects', 'students', 'faculty']
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        flash("All system data has been safely reset.", "success")
    except Exception as e:
        flash(f"Error resetting data: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/student-report/<enrollment_no>')
def student_report_view(enrollment_no):
    from analysis import get_student_details, get_student_marks, calculate_student_summary, generate_student_charts_new
    student = get_student_details(enrollment_no)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('admin.view_students'))
    
    marks_list = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    generate_student_charts_new(enrollment_no)
    
    return render_template('admin/student_detail.html', student=student, marks_list=marks_list, summary=summary)

@admin_bp.route('/profile')
def profile():
    return render_template('admin/admin_profile.html', email=session.get('admin_email'))

@admin_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        old_pw = request.form.get('old_password')
        new_pw = request.form.get('new_password')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE email = %s", (session.get('admin_email'),))
        admin = cursor.fetchone()
        
        if admin and check_password_hash(admin['password'], old_pw):
            hashed = generate_password_hash(new_pw)
            cursor.execute("UPDATE admin SET password = %s WHERE email = %s", (hashed, admin['email']))
            conn.commit()
            flash("Password updated successfully!", "success")
        else:
            flash("Invalid current password.", "danger")
        cursor.close()
        conn.close()
    return render_template('admin/change_password.html')
