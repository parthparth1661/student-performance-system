from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from analysis import get_dashboard_stats, generate_dashboard_charts, get_performance_overview
from datetime import date, datetime
import os
import math
import smtplib
import re
from email.mime.text import MIMEText

admin_bp = Blueprint('admin', __name__)

# --- Authentication Protection ---
@admin_bp.before_request
def check_admin_login():
    if request.endpoint in ['admin.login', 'admin.logout', 'admin.static']: 
        return
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email') or request.form.get('username') 
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('admin/admin_login.html')
            
        cursor = conn.cursor(dictionary=True)

        if not email or not password:
            flash("Operations Aborted: All credentials are required.", "warning")
            return render_template('admin/admin_login.html')
            
        try:
            cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
            admin = cursor.fetchone()
            if admin and check_password_hash(admin['password'], password):
                session.permanent = True
                session['admin_id'] = admin['admin_id']
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
    # 🎯 🧠 STEP 1: GET FILTER VALUES
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'attendance': request.args.get('attendance'),
        'subject': request.args.get('subject')
    }

    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    # 📊 🧬 STEP 2: GENERATE ANALYTICS & CHARTS
    stats = get_dashboard_stats(filters)
    chart_paths = generate_dashboard_charts(filters)
    
    # 📋 🧬 STEP 3: FETCH NEW ANALYTICS (TOP PERFORMERS & ALERTS)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Top Performers
    cursor.execute("""
        SELECT s.name, AVG(m.total_marks) as avg_marks
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        GROUP BY s.enrollment_no
        ORDER BY avg_marks DESC
        LIMIT 5
    """)
    top_students = cursor.fetchall()

    # 2. Low Performance Alerts (Combined)
    # Marks < 40
    cursor.execute("""
        SELECT DISTINCT s.name, 'Low Marks' as reason
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        WHERE m.total_marks < 40
    """)
    low_marks = cursor.fetchall()

    # Attendance < 75%
    cursor.execute("""
        SELECT s.name, 'Low Attendance' as reason
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        GROUP BY s.enrollment_no
        HAVING (SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END)*100.0/COUNT(*)) < 75
    """)
    low_attendance = cursor.fetchall()
    
    # Merge and deduplicate alerts (preferring showing both if applicable, but keep it simple)
    alerts_dict = {}
    for entry in low_marks:
        alerts_dict[entry['name']] = "Critical Marks"
    for entry in low_attendance:
        if entry['name'] in alerts_dict:
            alerts_dict[entry['name']] += " & Attendance"
        else:
            alerts_dict[entry['name']] = "Low Attendance"
    
    low_students = [{'name': name, 'reason': reason} for name, reason in alerts_dict.items()]

    # Fetch all subjects for the filter dropdown
    cursor.execute("SELECT DISTINCT subject_name FROM subjects ORDER BY subject_name ASC")
    all_subjects = [r['subject_name'] for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    return render_template('admin/admin_dashboard.html', 
                         stats=stats, 
                         filters=filters, 
                         charts=chart_paths,
                         top_students=top_students,
                         low_students=low_students,
                         subjects=all_subjects,
                         today_date=date.today().strftime('%d %b %Y'))

# --- 🧑🎓 1. STUDENTS MODULE ---
@admin_bp.route('/students')
def view_students():
    department = request.args.get('department')
    semester = request.args.get('semester')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    if department:
        query += " AND department = %s"
        params.append(department)
    if semester:
        query += " AND semester = %s"
        params.append(semester)
    if search:
        query += " AND (name LIKE %s OR enrollment_no LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    # Get total count for pagination
    count_query = "SELECT COUNT(*) as total FROM (" + query + ") as t"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / limit)

    # Get paginated data
    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    cursor.execute(query, params)
    students = cursor.fetchall()
    
    conn.close()
    return render_template('admin/view_students.html', 
                          students=students, 
                          page=page, 
                          total_pages=total_pages,
                          total_students=total_records,
                          filters={'department': department, 'semester': semester, 'search': search})

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
        
        # 1️⃣ FIELD VALIDATION
        if not all([enrollment_no, name, email, department, semester]):
            flash("Operation Aborted: All student fields are mandatory.", "danger")
            return render_template('admin/add_student.html')

        try:
            # 2️⃣ DUPLICATE PREVENTION
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no = %s", (enrollment_no,))
            if cursor.fetchone():
                flash(f"System Conflict: Student with ID {enrollment_no} is already registered.", "warning")
                return render_template('admin/add_student.html')

            pw_hash = generate_password_hash(enrollment_no + "@123")
            cursor.execute("""
                INSERT INTO students (enrollment_no, name, email, department, semester, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (enrollment_no, name, email, department, semester, pw_hash))
            

            
            conn.commit()
            flash("Student record successfully established.", "success")
            return redirect(url_for('admin.view_students'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()
    return render_template('admin/add_student.html')

@admin_bp.route('/students/edit/<enrollment_no>', methods=['GET', 'POST'])
def edit_student(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']
        
        try:
            cursor.execute("""
                UPDATE students 
                SET name=%s, email=%s, department=%s, semester=%s 
                WHERE enrollment_no=%s
            """, (name, email, department, semester, enrollment_no))
            conn.commit()
            flash("Student details updated!", "success")
            return redirect(url_for('admin.view_students'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
    student = cursor.fetchone()
    # Safely handle missing profile entries during dev migration if any
    if not student:
        flash("Student Identity Record not found.", "warning")
        return redirect(url_for('admin.view_students'))
    conn.close()
    
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('admin.view_students'))
        
    return render_template('admin/add_student.html', student=student, edit_mode=True)

@admin_bp.route('/students/delete/<enrollment_no>')
def delete_student(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE enrollment_no = %s", (enrollment_no,))
        conn.commit()
        flash("Student deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_students'))

# --- 📚 2. SUBJECTS MODULE ---
@admin_bp.route('/subjects')
def view_subjects():
    department = request.args.get('department')
    semester = request.args.get('semester')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT s.*, f.faculty_name 
        FROM subjects s 
        LEFT JOIN faculty f ON s.faculty_id = f.faculty_id
        WHERE 1=1
    """
    params = []

    if department and department != 'All':
        query += " AND s.department = %s"
        params.append(department)
    
    if semester and semester != 'All':
        query += " AND s.semester = %s"
        params.append(semester)
        
    if search:
        query += " AND s.subject_name LIKE %s"
        params.append(f"%{search}%")

    # Count for pagination
    count_query = query.replace("s.*, f.faculty_name", "COUNT(*)")
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['COUNT(*)']
    total_pages = math.ceil(total_records / limit)

    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    subjects = cursor.fetchall()
    conn.close()
    
    return render_template('admin/view_subjects.html', 
                          subjects=subjects, 
                          page=page, 
                          total_pages=total_pages,
                          filters={'department': department, 'semester': semester, 'search': search})

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
        
        # 1️⃣ FIELD VALIDATION
        if not all([subject_name, department, semester]):
            flash("Input Error: Subject name, department, and semester are required.", "danger")
            return render_template('admin/add_subject.html', faculties=faculties)
            
        try:
            # 2️⃣ DUPLICATE PREVENTION
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_name=%s AND department=%s AND semester=%s", (subject_name, department, semester))
            if cursor.fetchone():
                flash(f"Catalogue Conflict: '{subject_name}' already exists for {department} Sem {semester}.", "warning")
                return render_template('admin/add_subject.html', faculties=faculties)

            cursor.execute("""
                INSERT INTO subjects (subject_name, department, semester, faculty_id)
                VALUES (%s, %s, %s, %s)
            """, (subject_name, department, semester, faculty_id))
            
            conn.commit()
            flash("Curriculum successfully updated with new subject.", "success")
            return redirect(url_for('admin.view_subjects'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_subject.html', faculties=faculties)

@admin_bp.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
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
                UPDATE subjects 
                SET subject_name=%s, department=%s, semester=%s, faculty_id=%s
                WHERE subject_id=%s
            """, (subject_name, department, semester, faculty_id, subject_id))
            conn.commit()
            flash("Subject updated!", "success")
            return redirect(url_for('admin.view_subjects'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            
    cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (subject_id,))
    subject = cursor.fetchone()
    conn.close()
    return render_template('admin/add_subject.html', subject=subject, faculties=faculties, edit_mode=True)

@admin_bp.route('/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        conn.commit()
        flash("Subject deleted!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_subjects'))

@admin_bp.route('/faculty/delete/<int:faculty_id>')
def delete_faculty(faculty_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM faculty WHERE faculty_id = %s", (faculty_id,))
        conn.commit()
        flash("Faculty member and their subject associations removed successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_faculty'))

# --- 👨‍🏫 3. FACULTY MODULE ---
@admin_bp.route('/faculty')
def view_faculty():
    department = request.args.get('department')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Complex query to get faculty with their mapped subjects
    query = """
        SELECT f.*, GROUP_CONCAT(sub.subject_name SEPARATOR ', ') as subjects_mapped
        FROM faculty f
        LEFT JOIN subjects sub ON f.faculty_id = sub.faculty_id
        WHERE 1=1
    """
    params = []

    if department and department != 'All':
        query += " AND f.department = %s"
        params.append(department)
        
    if search:
        query += " AND (f.faculty_name LIKE %s OR f.email LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " GROUP BY f.faculty_id"

    # Count for pagination
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    faculty_list = cursor.fetchall()
    conn.close()
    
    return render_template('admin/view_faculty.html', 
                          faculty=faculty_list, 
                          page=page, 
                          total_pages=total_pages,
                          filters={'department': department, 'search': search})

@admin_bp.route('/faculty/add', methods=['GET', 'POST'])
def add_faculty():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Smart Initial Fetch: Only fetch subjects for the selected department
    subjects = []
    # If it's a validation retry, we might have a department in the form
    active_dept = request.form.get('department')
    if active_dept and active_dept != "":
        cursor.execute("SELECT subject_id, subject_name, department FROM subjects WHERE department = %s", (active_dept,))
        subjects = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        contact_no = request.form['contact_no']
        subject_id = request.form.get('subject_id')
        
        # 🔒 STRICT INDIAN MOBILE VALIDATION
        if not re.match(r'^[6-9][0-9]{9}$', contact_no):
            flash("Validation Failed: Please enter a valid 10-digit Indian contact number starting with 6-9.", "danger")
            return redirect(request.url)
            
        try:
            cursor.execute("""
                INSERT INTO faculty (faculty_name, email, department, contact_no)
                VALUES (%s, %s, %s, %s)
            """, (name, email, department, contact_no))
            new_faculty_id = cursor.lastrowid
            
            # Map the subject if selected
            if subject_id:
                cursor.execute("UPDATE subjects SET faculty_id = %s WHERE subject_id = %s", (new_faculty_id, subject_id))
            
            conn.commit()
            flash("Faculty added and subject mapped successfully!", "success")
            return redirect(url_for('admin.view_faculty'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_faculty.html', subjects=subjects)

@admin_bp.route('/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
def edit_faculty(faculty_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Smart Initial Fetch: Fetch subjects for this faculty's current department
    cursor.execute("SELECT department FROM faculty WHERE faculty_id = %s", (faculty_id,))
    f_rec = cursor.fetchone()
    current_dept = f_rec['department'] if f_rec else None
    
    cursor.execute("SELECT subject_id, subject_name, department FROM subjects WHERE department = %s", (current_dept,))
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        contact_no = request.form['contact_no']
        subject_id = request.form.get('subject_id')
        
        # 🔒 STRICT INDIAN MOBILE VALIDATION
        if not re.match(r'^[6-9][0-9]{9}$', contact_no):
            flash("Validation Failed: Please enter a valid 10-digit Indian contact number starting with 6-9.", "danger")
            return redirect(request.url)
            
        try:
            cursor.execute("""
                UPDATE faculty 
                SET faculty_name=%s, email=%s, department=%s, contact_no=%s
                WHERE faculty_id=%s
            """, (name, email, department, contact_no, faculty_id))
            
            # Reset previous mapping if we want to ensure only one mapping or just add
            if subject_id:
                # Update the selected subject to this faculty
                cursor.execute("UPDATE subjects SET faculty_id = %s WHERE subject_id = %s", (faculty_id, subject_id))
            
            conn.commit()
            flash("Faculty details and subject mapping updated!", "success")
            return redirect(url_for('admin.view_faculty'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            
    cursor.execute("SELECT * FROM faculty WHERE faculty_id = %s", (faculty_id,))
    f_data = cursor.fetchone()
    
    # Get currently mapped subject ID (assuming primary)
    cursor.execute("SELECT subject_id FROM subjects WHERE faculty_id = %s LIMIT 1", (faculty_id,))
    mapped_sub = cursor.fetchone()
    current_subject_id = mapped_sub['subject_id'] if mapped_sub else None
    
    conn.close()
    return render_template('admin/add_faculty.html', faculty=f_data, subjects=subjects, current_subject_id=current_subject_id, edit_mode=True)

@admin_bp.route('/faculty/analytics')
def faculty_analytics():
    filters = {'department': request.args.get('department')}
    from analysis import get_faculty_analytics, generate_faculty_performance_charts
    
    analytics_data = get_faculty_analytics(filters)
    generate_faculty_performance_charts(analytics_data)
    
    return render_template('admin/faculty_analytics.html', 
                          analytics=analytics_data, 
                          filters=filters)

@admin_bp.route('/faculty/profile/<int:faculty_id>')
def faculty_profile_view(faculty_id):
    from analysis import get_single_faculty_detail
    data = get_single_faculty_detail(faculty_id)
    if not data:
        flash("Faculty profile not found.", "danger")
        return redirect(url_for('admin.view_faculty'))
    
    return render_template('admin/faculty_detail.html', 
                          profile=data['profile'], 
                          subjects=data['subjects'])

# --- 📊 4. MARKS MODULE ---
@admin_bp.route('/marks')
def view_marks():
    enrollment = request.args.get('enrollment')
    department = request.args.get('department')
    semester = request.args.get('semester')
    subject_id = request.args.get('subject_id')
    exam_type = request.args.get('exam_type')
    
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Base query for marks with joins for filtering
    query = """
        SELECT m.*, s.name as student_name, sub.subject_name, sub.department, sub.semester
        FROM marks m
        JOIN students s ON m.enrollment_no = s.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        WHERE 1=1
    """
    params = []

    if enrollment:
        query += " AND (m.enrollment_no LIKE %s OR s.name LIKE %s)"
        params.extend([f"%{enrollment}%", f"%{enrollment}%"])
    
    if department and department != 'All':
        query += " AND sub.department = %s"
        params.append(department)
        
    if semester and semester != 'All':
        query += " AND sub.semester = %s"
        params.append(semester)

    if subject_id and subject_id != 'All':
        query += " AND m.subject_id = %s"
        params.append(subject_id)
        
    if exam_type and exam_type != 'All':
        query += " AND m.exam_type = %s"
        params.append(exam_type)

    # 📊 Calculate Summary Stats for the CURRENT FILTERED SET
    stats_query = f"""
        SELECT 
            COUNT(*) as total_entries,
            AVG(total_marks) as avg_marks,
            MAX(total_marks) as top_score,
            SUM(CASE WHEN total_marks >= 40 THEN 1 ELSE 0 END) as pass_count
        FROM ({query}) as filtered_marks
    """
    cursor.execute(stats_query, params)
    marks_stats = cursor.fetchone()

    # Calculate total records for pagination
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    query += " ORDER BY m.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    marks_list = cursor.fetchall()
    
    # Post-process for display
    for m in marks_list:
        m['marks_id'] = m['id']

    # Fetch subjects for filter dropdown
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()

    # 📊 Calculate Subject-wise Averages for Chart
    cursor.execute("""
        SELECT sub.subject_name, AVG(m.total_marks) as avg_marks
        FROM marks m
        JOIN subjects sub ON m.subject_id = sub.subject_id
        GROUP BY m.subject_id
        ORDER BY avg_marks DESC
    """)
    subject_averages = cursor.fetchall()
    chart_labels = [row['subject_name'] for row in subject_averages]
    chart_values = [float(row['avg_marks']) for row in subject_averages]

    conn.close()
    return render_template('admin/view_marks.html', 
                          marks_list=marks_list, 
                          subjects=all_subjects,
                          stats=marks_stats,
                          chart_data={'labels': chart_labels, 'values': chart_values},
                          page=page, 
                          total_pages=total_pages,
                          total_records=total_records,
                          filters={
                              'enrollment': enrollment, 
                              'department': department,
                              'semester': semester,
                              'subject_id': subject_id, 
                              'exam_type': exam_type
                          })

@admin_bp.route('/get-subjects')
def get_subjects_api():
    department = request.args.get('department')
    semester = request.args.get('semester')
    
    if not (department and semester):
        return {"error": "Missing params"}, 400
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()
    conn.close()
    return {"subjects": subjects}

@admin_bp.route('/get-subjects-by-department')
def get_subjects_by_department():
    department = request.args.get('department')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM subjects WHERE department = %s", (department,))
    subjects = cursor.fetchall()
    conn.close()
    return jsonify(subjects)

@admin_bp.route('/get-students-api')
def get_students_api():
    department = request.args.get('department')
    semester = request.args.get('semester')
    
    if not (department and semester):
        return {"error": "Missing params"}, 400
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s", (department, semester))
    students = cursor.fetchall()
    conn.close()
    return {"students": students}

@admin_bp.route('/add_marks', methods=['GET', 'POST'])
@admin_bp.route('/marks/add', methods=['GET', 'POST'])
def add_marks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 🎯 STEP 1 & 2: Get filters from URL args
    selected_dept = request.args.get('department')
    selected_sem = request.args.get('semester')
    
    students = []
    subjects = []
    
    if selected_dept and selected_sem:
        # 🎯 STEP 2: FETCH STUDENTS BASED ON SELECTION
        cursor.execute("""
            SELECT enrollment_no, name 
            FROM students 
            WHERE department = %s AND semester = %s 
            ORDER BY enrollment_no
        """, (selected_dept, selected_sem))
        students = cursor.fetchall()
        
        # 🎯 STEP 3: FETCH SUBJECTS
        cursor.execute("""
            SELECT subject_id, subject_name 
            FROM subjects 
            WHERE department = %s AND semester = %s 
            ORDER BY subject_name
        """, (selected_dept, selected_sem))
        subjects = cursor.fetchall()
    
    # If no results found with filters, but filters were sent, flash a warning
    if (selected_dept or selected_sem) and not (students or subjects):
        if selected_dept and selected_sem:
            flash(f"No active Student/Subject context found for {selected_dept} Sem {selected_sem}.", "warning")
    
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        subject_id = request.form['subject_id']
        internal_marks = request.form.get('internal_marks', 0)
        viva_marks = request.form.get('viva_marks', 0)
        external_marks = request.form.get('external_marks', 0)
        
        # 1️⃣ FIELD VALIDATION (STRICT)
        if not all([enrollment_no, subject_id]):
            flash("Security Alert: Missing critical performance data fields.", "danger")
            return render_template('admin/add_marks.html', students=students, subjects=subjects)
        else:
            try:
                i_m = float(internal_marks)
                v_m = float(request.form.get('viva_marks', 0))
                e_m = float(external_marks)
                
                # 🧱 STEP 1 & 5 — VALIDATION (Standard Academic Limits)
                if not (0 <= i_m <= 30):
                    flash("Invalid Score: Internal marks cannot exceed 30.", "danger")
                elif not (0 <= v_m <= 20):
                    flash("Invalid Score: Viva marks cannot exceed 20.", "danger")
                elif not (0 <= e_m <= 50):
                    flash("Invalid Score: External marks cannot exceed 50.", "danger")
                else:
                    # 🧱 STEP 2 — TOTAL CALCULATION (30 + 20 + 50 = 100)
                    total_marks = i_m + v_m + e_m
                    
                    # 🧱 STEP 3 — PASS / FAIL LOGIC
                    # Rule: Total >= 40 AND External >= 20
                    result = 'Pass' if (total_marks >= 40 and e_m >= 20) else 'Fail'
                    # 🛡️ PREVENT DUPLICATE ENTRY (Fixed for new schema)
                    cursor.execute("""
                        SELECT * FROM marks 
                        WHERE enrollment_no = %s AND subject_id = %s
                    """, (enrollment_no, subject_id))
                    
                    if cursor.fetchone():
                        flash(f"Duplicate Entry Warning: Record already exists for Student {enrollment_no} in this subject.", "warning")
                    else:
                        # 🧱 STEP 4 — INSERT QUERY
                        cursor.execute("""
                            INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks, result)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (enrollment_no, subject_id, i_m, v_m, e_m, total_marks, result))
                        
                        conn.commit()
                        flash(f"Record for {enrollment_no} registered successfully!", "success")
                        # 🎯 Redirect back with filters for structured entry
                        return redirect(url_for('admin.add_marks', department=selected_dept, semester=selected_sem))
            except ValueError:
                flash("Invalid numeric value for marks.", "danger")
            except Exception as e:
                flash(f"Database Error: {e}", "danger")
    
    return render_template('admin/add_marks.html', 
                          students=students, 
                          subjects=subjects, 
                          selected_dept=selected_dept, 
                          selected_sem=selected_sem)

@admin_bp.route('/edit_marks/<int:marks_id>', methods=['GET', 'POST'])
@admin_bp.route('/marks/edit/<int:marks_id>', methods=['GET', 'POST'])
def edit_marks(marks_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            i_m = float(request.form.get('internal_marks', 0))
            v_m = float(request.form.get('viva_marks', 0))
            e_m = float(request.form.get('external_marks', 0))
            
            # 🧱 STEP 1 & 5 — VALIDATION (Standard Academic Limits)
            if not (0 <= i_m <= 30) or not (0 <= v_m <= 20) or not (0 <= e_m <= 50):
                flash("Validation Error: Component scores exceed limits (Int: 30, Viva: 20, Ext: 50)", "danger")
            else:
                total_marks = i_m + v_m + e_m
                # 🧱 STEP 3 — PASS / FAIL LOGIC
                result = 'Pass' if (total_marks >= 40 and e_m >= 20) else 'Fail'
                
                if total_marks > 100:
                    flash("Invalid marks: Total cannot exceed 100", "danger")
                else:
                    cursor.execute("""
                        UPDATE marks 
                        SET internal_marks=%s, viva_marks=%s, external_marks=%s, total_marks=%s, result=%s
                        WHERE id = %s
                    """, (i_m, v_m, e_m, total_marks, result, marks_id))
                    
                    conn.commit()
                    flash("Academic record updated successfully!", "success")
                    return redirect(url_for('admin.view_marks'))
        except Exception as e:
            flash(f"Update Error: {e}", "danger")

    cursor.execute("""
        SELECT m.*, s.name as student_name, sub.subject_name 
        FROM marks m
        JOIN students s ON m.enrollment_no = s.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        WHERE m.id = %s
    """, (marks_id,))
    mark_data = cursor.fetchone()
    conn.close()
    
    if not mark_data:
        flash("Record not found.", "danger")
        return redirect(url_for('admin.view_marks'))
        
    return render_template('admin/add_marks.html', mark=mark_data, edit_mode=True)

@admin_bp.route('/delete_marks/<int:marks_id>')
@admin_bp.route('/marks/delete/<int:marks_id>')
def delete_marks(marks_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM marks WHERE id = %s", (marks_id,))
        conn.commit()
        flash("Marks record permanently removed.", "success")
    except Exception as e:
        flash(f"Deletion Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_marks'))

# --- 🛰️ 5. ATTENDANCE MODULE ---
@admin_bp.route('/attendance')
def view_attendance():
    enrollment = request.args.get('enrollment')
    department = request.args.get('department')
    semester = request.args.get('semester')
    subject_id = request.args.get('subject_id')
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Base query with joins
    query = """
        SELECT a.*, s.name as student_name, sub.subject_name, sub.department, sub.semester
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        JOIN subjects sub ON a.subject_id = sub.subject_id
        WHERE 1=1
    """
    params = []

    if enrollment:
        query += " AND (a.enrollment_no LIKE %s OR s.name LIKE %s)"
        params.extend([f"%{enrollment}%", f"%{enrollment}%"])
    
    if department and department != 'All':
        query += " AND sub.department = %s"
        params.append(department)
        
    if semester and semester != 'All':
        query += " AND sub.semester = %s"
        params.append(semester)

    if subject_id and subject_id != 'All':
        query += " AND a.subject_id = %s"
        params.append(subject_id)
        
    if status_filter and status_filter != 'All':
        query += " AND a.status = %s"
        params.append(status_filter)

    if date_filter:
        query += " AND a.date = %s"
        params.append(date_filter)

    # 📊 Calculate Summary Stats
    stats_query = f"""
        SELECT 
            COUNT(*) as total_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM ({query}) as filtered_att
    """
    cursor.execute(stats_query, params)
    att_stats = cursor.fetchone()
    
    # Calculate Attendance %
    if att_stats and att_stats['total_classes'] > 0:
        att_stats['percent'] = round((att_stats['present_count'] / att_stats['total_classes']) * 100, 2)
    else:
        att_stats = {'total_classes': 0, 'present_count': 0, 'absent_count': 0, 'percent': 0}

    # ⚠️ ALERT SYSTEM: Identify low attendance students (<75%)
    # We check across all students in the selected department/semester context
    alert_query = """
        SELECT s.name, s.enrollment_no,
        (SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(a.attendance_id), 0)) as attendance_pct
        FROM students s
        LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
        JOIN subjects sub ON 1=1 -- Placeholder to allow filtering by subject if needed, but usually alerts are global
    """
    # Simplified alert for now to avoid complex group by logic errors during filtration
    cursor.execute("""
        SELECT s.name, s.enrollment_no,
        (SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(a.attendance_id), 0)) as attendance_pct
        FROM students s
        JOIN attendance a ON s.enrollment_no = a.enrollment_no
        GROUP BY s.enrollment_no
        HAVING attendance_pct < 75
    """)
    low_attendance_students = cursor.fetchall()
    low_att_count = len(low_attendance_students)
    low_att_ids = [s['enrollment_no'] for s in low_attendance_students]

    # Pagination data
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    # Fetch final paginated data
    query += " ORDER BY a.date DESC, a.attendance_id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    cursor.execute(query, params)
    attendance_list = cursor.fetchall()

    # Helpers
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()
    
    cursor.execute("SELECT enrollment_no, name FROM students ORDER BY enrollment_no")
    all_students = cursor.fetchall()
    
    conn.close()
    return render_template('admin/view_attendance.html', 
                          attendance_list=attendance_list, 
                          subjects=all_subjects,
                          students=all_students,
                          stats=att_stats,
                          low_att_count=low_att_count,
                          low_att_ids=low_att_ids,
                          page=page, 
                          total_pages=total_pages,
                          datetime=datetime,
                          filters={
                              'enrollment': enrollment, 
                              'department': department,
                              'semester': semester,
                              'subject_id': subject_id,
                              'status': status_filter,
                              'date': date_filter
                          })

@admin_bp.route('/attendance/report')
def attendance_report():
    department = request.args.get('department', 'BCA')
    semester = request.args.get('semester', '1')
    subject_id = request.args.get('subject_id')
    month_val = request.args.get('month', datetime.now().month, type=int)
    year_val = request.args.get('year', datetime.now().year, type=int)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch Subjects for Filter
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()

    if not subject_id and subjects:
        subject_id = subjects[0]['subject_id']

    report_data = []
    stats = {'total_lectures': 0, 'avg_pct': 0, 'low_att': 0}

    if subject_id:
        # 2. Advanced Aggregation Query
        query = """
            SELECT 
                s.name, s.enrollment_no,
                COUNT(a.attendance_id) as total_lectures,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                GROUP_CONCAT(CASE WHEN a.status = 'Absent' THEN DATE_FORMAT(a.date, '%d %b') END ORDER BY a.date ASC SEPARATOR ', ') as absent_dates
            FROM students s
            JOIN attendance a ON s.enrollment_no = a.enrollment_no
            WHERE a.subject_id = %s AND MONTH(a.date) = %s AND YEAR(a.date) = %s
            GROUP BY s.enrollment_no
        """
        cursor.execute(query, (subject_id, month_val, year_val))
        report_data = cursor.fetchall()

        # 3. Calculate Report-wide Stats
        if report_data:
            total_lectures_set = set(r['total_lectures'] for r in report_data)
            stats['total_lectures'] = max(total_lectures_set) if total_lectures_set else 0
            
            total_pct = 0
            for r in report_data:
                r['pct'] = round((r['present_count'] / r['total_lectures'] * 100), 1) if r['total_lectures'] > 0 else 0
                total_pct += r['pct']
                if r['pct'] < 75:
                    stats['low_att'] += 1
            stats['avg_pct'] = round(total_pct / len(report_data), 1)

    conn.close()
    return render_template('admin/attendance_report.html', 
                          report=report_data, 
                          subjects=subjects, 
                          stats=stats,
                          datetime=datetime,
                          filters={
                              'department': department,
                              'semester': semester,
                              'subject_id': int(subject_id) if subject_id else None,
                              'month': month_val,
                              'year': year_val
                          })

@admin_bp.route('/attendance/bulk', methods=['GET', 'POST'])
def bulk_attendance():
    department = request.args.get('department', 'BCA')
    semester = request.args.get('semester', '1')
    subject_id = request.args.get('subject_id')
    att_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch Subjects for Context
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()
    
    if not subject_id and subjects:
        subject_id = subjects[0]['subject_id']

    # 2. Fetch Students for Context
    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s ORDER BY enrollment_no", (department, semester))
    students = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        att_date = request.form.get('date')
        
        if not subject_id or not att_date:
            flash("Context Error: Subject and Date must be identified.", "danger")
        else:
            success_count = 0
            for s in students:
                status = request.form.get(f"status_{s['enrollment_no']}")
                if status:
                    # 🛡️ Duplicate Check
                    cursor.execute("SELECT * FROM attendance WHERE enrollment_no=%s AND subject_id=%s AND date=%s", (s['enrollment_no'], subject_id, att_date))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)", 
                                       (s['enrollment_no'], subject_id, att_date, status))
                        success_count += 1
            
            conn.commit()
            if success_count > 0:
                flash(f"Success: {success_count} attendance records synchronized successfully!", "success")
            else:
                flash("Information: No new records were added (Records may already exist).", "info")
            return redirect(url_for('admin.view_attendance'))

    conn.close()
    return render_template('admin/bulk_attendance.html', 
                          students=students, 
                          subjects=subjects, 
                          today=att_date,
                          filters={
                              'department': department,
                              'semester': semester,
                              'subject_id': int(subject_id) if subject_id else None
                          })

@admin_bp.route('/add_attendance', methods=['GET', 'POST'])
def add_attendance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT enrollment_no, name FROM students ORDER BY enrollment_no")
    students = cursor.fetchall()
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        subject_id = request.form['subject_id']
        att_date = request.form['date']
        status = request.form['status']
        
        # 1️⃣ FIELD VALIDATION
        if not all([enrollment_no, subject_id, att_date, status]):
            flash("Compliance Alert: All attendance registry fields must be populated.", "danger")
            return render_template('admin/add_attendance.html', students=students, subjects=subjects, today=date.today().strftime('%Y-%m-%d'))

        # 2️⃣ STATUS VALIDATION
        if status not in ['Present', 'Absent']:
            flash("Sanity Check Failed: Invalid attendance status detected.", "danger")
            return render_template('admin/add_attendance.html', students=students, subjects=subjects, today=date.today().strftime('%Y-%m-%d'))

        else:
            # 🛡️ PREVENT DUPLICATE ENTRY (same student + subject + date)
            cursor.execute("""
                SELECT * FROM attendance 
                WHERE enrollment_no = %s AND subject_id = %s AND date = %s
            """, (enrollment_no, subject_id, att_date))
            
            if cursor.fetchone():
                flash(f"Duplicate Error: Attendance already marked for {enrollment_no} on {att_date} for this subject.", "warning")
            else:
                try:
                    cursor.execute("""
                        INSERT INTO attendance (enrollment_no, subject_id, date, status)
                        VALUES (%s, %s, %s, %s)
                    """, (enrollment_no, subject_id, att_date, status))
                    
                    conn.commit()
                    flash(f"Attendance for {enrollment_no} recorded successfully!", "success")
                    return redirect(url_for('admin.view_attendance'))
                except Exception as e:
                    flash(f"System Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_attendance.html', 
                          students=students, 
                          subjects=subjects, 
                          today=date.today().strftime('%Y-%m-%d'))

@admin_bp.route('/edit_attendance/<int:attendance_id>', methods=['GET', 'POST'])
def edit_attendance(attendance_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        status = request.form['status']
        try:
            cursor.execute("UPDATE attendance SET status=%s WHERE attendance_id=%s", (status, attendance_id))
            conn.commit()
            flash("Attendance status updated.", "success")
            return redirect(url_for('admin.view_attendance'))
        except Exception as e:
            flash(f"Update Error: {e}", "danger")

    cursor.execute("""
        SELECT a.*, s.name as student_name, sub.subject_name 
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        JOIN subjects sub ON a.subject_id = sub.subject_id
        WHERE a.attendance_id = %s
    """, (attendance_id,))
    record = cursor.fetchone()
    conn.close()
    
    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for('admin.view_attendance'))
        
    return render_template('admin/add_attendance.html', record=record, edit_mode=True)

@admin_bp.route('/delete_attendance/<int:attendance_id>')
def delete_attendance(attendance_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM attendance WHERE attendance_id = %s", (attendance_id,))
        conn.commit()
        flash("Attendance record deleted successfully", "success")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_attendance'))
@admin_bp.route('/clear-attendance')
def clear_attendance():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE attendance")
        conn.commit()
        conn.close()
        flash("All attendance records have been deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: Could not clear attendance registry ({e})", "danger")
    return redirect(url_for('admin.view_attendance'))

@admin_bp.route('/clear-subjects')
def clear_subjects():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE subjects")
        conn.commit()
        conn.close()
        flash("All subject records have been deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: Could not clear subject registry ({e})", "danger")
    return redirect(url_for('admin.view_subjects'))

@admin_bp.route('/clear-students')
def clear_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE students")
        conn.commit()
        conn.close()
        flash("All student records have been deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: Could not clear student registry ({e})", "danger")
    return redirect(url_for('admin.view_students'))

@admin_bp.route('/clear-marks')
def clear_marks():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE marks")
        conn.commit()
        conn.close()
        flash("All marks records have been deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: Could not clear marks registry ({e})", "danger")
    return redirect(url_for('admin.view_marks'))

@admin_bp.route('/clear-faculty')
def clear_faculty():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE faculty")
        conn.commit()
        conn.close()
        flash("All faculty records have been deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: Could not clear faculty registry ({e})", "danger")
    return redirect(url_for('admin.view_faculty'))

# --- 🛰️ BULK & SYSTEM ROUTES ---

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
# --- 📊 POWERFUL INSTITUTIONAL REPORT CENTER (v2.0) ---

@admin_bp.route('/reports')
def reports_marks():
    # 🎯 🧠 STEP 1: FILTERS & PARAMETERS
    filters = {
        'department': request.args.get('department', 'All'),
        'semester': request.args.get('semester', 'All'),
        'subject': request.args.get('subject', 'All'),
        'search': request.args.get('search', '')
    }
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 🟡 1. BUILD DYNAMIC QUERY
    query = """
        SELECT s.name, s.enrollment_no, s.department, s.semester, 
               sub.subject_name, m.internal_marks, m.viva_marks, m.external_marks, m.total_marks
        FROM marks m
        JOIN students s ON m.enrollment_no = s.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
    """
    where_parts = []
    values = []
    
    if filters['department'] != 'All':
        where_parts.append("s.department = %s")
        values.append(filters['department'])
    if filters['semester'] != 'All':
        where_parts.append("s.semester = %s")
        values.append(filters['semester'])
    if filters['subject'] != 'All':
        where_parts.append("sub.subject_name = %s")
        values.append(filters['subject'])
    if filters['search']:
        where_parts.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
        search_val = f"%{filters['search']}%"
        values.extend([search_val, search_val])
        
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
        
    query += " ORDER BY s.enrollment_no ASC"
    
    cursor.execute(query, values)
    marks_data = cursor.fetchall()
    
    # 📊 2. SUMMARY KPI CALCULATIONS
    summary = {
        'avg_marks': 0,
        'pass_count': 0,
        'fail_count': 0,
        'top_performer': 'N/A'
    }
    
    if marks_data:
        total_m = [row['total_marks'] for row in marks_data]
        summary['avg_marks'] = round(sum(total_m) / len(total_m), 1)
        summary['pass_count'] = len([m for m in total_m if m >= 40])
        summary['fail_count'] = len(total_m) - summary['pass_count']
        
        # Determine Top Performer from this view
        top_row = max(marks_data, key=lambda x: x['total_marks'])
        summary['top_performer'] = top_row['name']
        
    # 📑 3. DROPDOWN DATA
    cursor.execute("SELECT DISTINCT department FROM students")
    depts = [r['department'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT subject_name FROM subjects")
    subjects_list = [r['subject_name'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template('admin/reports_marks.html', 
                           data=marks_data, 
                           summary=summary, 
                           filters=filters,
                           departments=depts,
                           subjects=subjects_list)

@admin_bp.route('/reports/student/<enrollment_no>')
def reports_student_detail(enrollment_no):
    from analysis import get_student_details, get_student_marks, calculate_student_summary
    student = get_student_details(enrollment_no)
    if not student:
        flash("Subject Profile Missing.", "danger")
        return redirect(url_for('admin.reports_marks'))
        
    marks = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    
    # Attendance Aggregate
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) as total, SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present
        FROM attendance WHERE enrollment_no = %s
    """, (enrollment_no,))
    att = cursor.fetchone()
    conn.close()
    
    att_percent = round((att['present'] / att['total'] * 100), 1) if att['total'] > 0 else 0
    
    return render_template('admin/reports_student_detail.html', 
                           student=student, 
                           marks=marks, 
                           summary=summary,
                           attendance={'percent': att_percent, 'total': att['total'], 'present': att['present']})

@admin_bp.route('/reports/attendance')
def reports_attendance():
    filters = {
        'department': request.args.get('department', 'All'),
        'semester': request.args.get('semester', 'All'),
        'search': request.args.get('search', '')
    }
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT s.name, s.enrollment_no, s.department, s.semester,
               COUNT(a.attendance_id) as total_classes,
               SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) as present_count
        FROM students s
        LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
    """
    where_parts = []
    values = []
    
    if filters['department'] != 'All':
        where_parts.append("s.department = %s")
        values.append(filters['department'])
    if filters['semester'] != 'All':
        where_parts.append("s.semester = %s")
        values.append(filters['semester'])
    if filters['search']:
        where_parts.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
        sv = f"%{filters['search']}%"
        values.extend([sv, sv])
        
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
        
    query += " GROUP BY s.enrollment_no ORDER BY s.enrollment_no ASC"
    
    cursor.execute(query, values)
    attendance_data = cursor.fetchall()
    
    # Calculate percentages for each
    for row in attendance_data:
        row['percent'] = round((row['present_count'] / row['total_classes'] * 100), 1) if row['total_classes'] > 0 else 0
        
    cursor.execute("SELECT DISTINCT department FROM students")
    depts = [r['department'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template('admin/reports_attendance.html', 
                           data=attendance_data, 
                           filters=filters, 
                           departments=depts)

# --- 📄 EXPORT PROTOCOLS ---

@admin_bp.route('/reports/export/<type>')
def reports_export(type):
    import csv
    from io import StringIO
    from flask import make_response
    
    # Simple CSV export logic for general reports
    report_type = request.args.get('report_type', 'marks')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if report_type == 'marks':
        cursor.execute("""
            SELECT s.name, s.enrollment_no, sub.subject_name, m.internal_marks, m.viva_marks, m.external_marks, m.total_marks
            FROM marks m
            JOIN students s ON m.enrollment_no = s.enrollment_no
            JOIN subjects sub ON m.subject_id = sub.subject_id
        """)
        filename = "Academic_Marks_Report.csv"
    else:
        cursor.execute("""
            SELECT s.name, s.enrollment_no, COUNT(a.attendance_id) as total, SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) as present
            FROM students s
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
            GROUP BY s.enrollment_no
        """)
        filename = "Attendance_Audit_Report.csv"
        
    data = cursor.fetchall()
    conn.close()
    
    if not data:
        flash("No data available for export.", "warning")
        return redirect(url_for('admin.reports_marks'))

    si = StringIO()
    cw = csv.DictWriter(si, fieldnames=data[0].keys())
    cw.writeheader()
    cw.writerows(data)
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv"
    return output


# --- 👤 ADMIN PROFILE MODULE ---
@admin_bp.route('/profile')
def profile():
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE admin_id = %s", (session.get('admin_id'),))
    admin_data = cursor.fetchone()
    conn.close()
    return render_template('admin/admin_profile.html', admin=admin_data)

@admin_bp.route('/update_profile', methods=['POST'])
def update_profile():
    name = request.form.get('name')
    email = request.form.get('email')
    old_email = session.get('admin_email')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE admin SET name=%s, email=%s WHERE email=%s", (name, email, old_email))
        conn.commit()
        session['admin_email'] = email
        flash("Identity Profile updated successfully!", "success")
    except Exception as e:
        flash(f"Profile update failed: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.profile'))

@admin_bp.route('/change_password', methods=['POST'])
def change_password():
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')
    
    if new_pw != confirm_pw:
        flash("New passwords do not match!", "danger")
        return redirect(url_for('admin.profile'))
        
    if not new_pw:
        flash("Mandatory credentials cannot be empty!", "danger")
        return redirect(url_for('admin.profile'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE email = %s", (session.get('admin_email'),))
    admin = cursor.fetchone()
    
    if admin and check_password_hash(admin['password'], current_pw):
        hashed = generate_password_hash(new_pw)
        cursor.execute("UPDATE admin SET password=%s WHERE email=%s", (hashed, admin['email']))
        conn.commit()
        flash("Security credentials updated successfully!", "success")
    else:
        flash("Identity verification failed. Current password incorrect.", "danger")
    
    conn.close()
    return redirect(url_for('admin.profile'))

# --- 💬 INSTITUTIONAL FEEDBACK MODULE ---
@admin_bp.route('/feedback')
def view_feedback():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Simple query matching standardized structure
    cursor.execute("SELECT * FROM feedback ORDER BY date DESC")
    feedback_data = cursor.fetchall()
    conn.close()
    
    return render_template('admin/view_feedback.html', feedback=feedback_data)

@admin_bp.route('/feedback/reply/<int:feedback_id>', methods=['POST'])
def reply_feedback(feedback_id):
    reply = request.form.get('admin_reply')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE feedback 
            SET admin_reply = %s 
            WHERE feedback_id = %s
        """, (reply, feedback_id))
        conn.commit()
        flash("Reply submitted successfully.", "success")
    except Exception as e:
        flash(f"Update failed: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('admin.view_feedback'))

@admin_bp.route('/feedback/delete/<int:feedback_id>')
def delete_feedback(feedback_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM feedback WHERE feedback_id = %s", (feedback_id,))
        conn.commit()
        flash("Feedback record deleted.", "success")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('admin.view_feedback'))
