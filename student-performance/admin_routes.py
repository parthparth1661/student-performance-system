from datetime import date, datetime
import os
import math
import csv
from io import StringIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from analysis import get_dashboard_stats, get_dashboard_chart_data, process_csv, get_faculty_analytics, get_report_data

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
                session['admin_id'] = admin['admin_id']
                session['admin_name'] = 'System Admin'
                flash(f"Institutional Synchronization Successful. Welcome back.", "success")
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
    # STEP 1: GET FILTER VALUES
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

    # STEP 2: GENERATE ANALYTICS
    stats = get_dashboard_stats(filters)
    chart_data = get_dashboard_chart_data(filters)
    
    # STEP 3: FETCH NEW ANALYTICS WITH FILTERS
    from analysis import build_dashboard_conditions
    where_clause, values = build_dashboard_conditions(filters)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Top Performers (Filtered)
    cursor.execute(f"""
        SELECT s.name, AVG(m.total_marks) as avg_marks
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        {where_clause}
        GROUP BY s.enrollment_no, s.name
        ORDER BY avg_marks DESC
        LIMIT 5
    """, values)
    top_students = cursor.fetchall()

    # 2. Risk Alerts (Filtered)
    cursor.execute(f"""
        SELECT DISTINCT s.name, 'Critical Score' as reason
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        {where_clause} AND m.total_marks < 40
    """, values)
    low_marks = cursor.fetchall()

    cursor.execute(f"""
        SELECT s.name, 'Low Attendance' as reason
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        LEFT JOIN subjects sub ON a.subject_id = sub.subject_id
        {where_clause}
        GROUP BY s.enrollment_no, s.name
        HAVING (SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*), 0)) < 75
    """, values)
    low_attendance = cursor.fetchall()
    
    # Merge and deduplicate alerts
    alerts_dict = {}
    for entry in low_marks:
        alerts_dict[entry['name']] = "Critical Marks"
    for entry in low_attendance:
        if entry['name'] in alerts_dict:
            alerts_dict[entry['name']] += " & Attendance"
        else:
            alerts_dict[entry['name']] = "Low Attendance"
    
    low_students = [{'name': name, 'reason': reason} for name, reason in alerts_dict.items()]

    # Subjects for dropdown
    cursor.execute("SELECT DISTINCT subject_name FROM subjects ORDER BY subject_name ASC")
    all_subjects = [r['subject_name'] for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    return render_template('admin/admin_dashboard.html', 
                         stats=stats, 
                         filters=filters, 
                         chart_data=chart_data,
                         top_students=top_students,
                         low_students=low_students,
                         subjects=all_subjects)

@admin_bp.route('/dashboard/api/stats')
def dashboard_api_stats():
    """API Endpoint for dynamic dashboard updates without page reloads"""
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'subject': request.args.get('subject')
    }
    
    # Get Core Stats & Charts
    stats = get_dashboard_stats(filters)
    chart_data = get_dashboard_chart_data(filters)
    
    # Get Filtered Leaderboard & Risks
    from analysis import build_dashboard_conditions
    where_clause, values = build_dashboard_conditions(filters)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Leaderboard
    cursor.execute(f"""
        SELECT s.name, AVG(m.total_marks) as avg_marks
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        {where_clause}
        GROUP BY s.enrollment_no, s.name
        ORDER BY avg_marks DESC
        LIMIT 5
    """, values)
    top_students = cursor.fetchall()

    # Risk alerts
    cursor.execute(f"""
        SELECT DISTINCT s.name, 'Critical Score' as reason
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        {where_clause} AND m.total_marks < 40
    """, values)
    low_marks = cursor.fetchall()

    cursor.execute(f"""
        SELECT s.name, 'Low Attendance' as reason
        FROM attendance a
        JOIN students s ON a.enrollment_no = s.enrollment_no
        LEFT JOIN subjects sub ON a.subject_id = sub.subject_id
        {where_clause}
        GROUP BY s.enrollment_no, s.name
        HAVING (SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*), 0)) < 75
    """, values)
    low_attendance = cursor.fetchall()
    
    # Merge alerts
    alerts_dict = {}
    for entry in low_marks: alerts_dict[entry['name']] = "Critical Marks"
    for entry in low_attendance:
        if entry['name'] in alerts_dict: alerts_dict[entry['name']] += " & Attendance"
        else: alerts_dict[entry['name']] = "Low Attendance"
    
    low_students = [{'name': name, 'reason': reason} for name, reason in alerts_dict.items()]
    
    cursor.close()
    conn.close()

    return jsonify({
        'stats': stats,
        'chart_data': chart_data,
        'top_students': top_students,
        'low_students': low_students
    })

# --- 1. STUDENTS MODULE ---
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
        import re
        enrollment_no = request.form['enrollment_no']
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']
        contact_no = request.form.get('contact_no', '')

        # 🇮🇳 Indian Mobile Validation (10 digits, starts with 6-9)
        if contact_no and not re.match(r'^[6-9]\d{9}$', contact_no):
            flash("Invalid Identity: Please enter a valid 10-digit Indian mobile number.", "warning")
            return render_template('admin/add_student.html', form_data=request.form)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Check Uniqueness
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no = %s", (enrollment_no,))
            if cursor.fetchone():
                flash("ID Conflict: Enrollment number already exists.", "danger")
                return render_template('admin/add_student.html', form_data=request.form)

            # 🛡️ Default Protocol: password = enrollment_no
            pw_hash = generate_password_hash(enrollment_no)
            cursor.execute("""
                INSERT INTO students (enrollment_no, name, email, department, semester, contact_no, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (enrollment_no, name, email, department, semester, contact_no, pw_hash))
            conn.commit()
            flash("Success: Student identity record established.", "success")
            return redirect(url_for('admin.view_students'))
        except Exception as e:
            flash(f"System Error: {e}", "danger")
        finally:
            conn.close()
    return render_template('admin/add_student.html')

@admin_bp.route('/students/edit/<enrollment_no>', methods=['GET', 'POST'])
def edit_student(enrollment_no):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        import re
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']
        contact_no = request.form.get('contact_no', '')

        # 🇮🇳 Indian Mobile Validation
        if contact_no and not re.match(r'^[6-9]\d{9}$', contact_no):
            flash("Invalid Identity: Please enter a valid 10-digit Indian mobile number.", "warning")
            student_data = dict(request.form)
            student_data['enrollment_no'] = enrollment_no
            return render_template('admin/add_student.html', student=student_data, edit_mode=True)
        
        try:
            cursor.execute("""
                UPDATE students 
                SET name=%s, email=%s, department=%s, semester=%s, contact_no=%s
                WHERE enrollment_no=%s
            """, (name, email, department, semester, contact_no, enrollment_no))
            conn.commit()
            flash("Profile Synchronized: Student record updated successfully.", "success")
            return redirect(url_for('admin.view_students'))
        except Exception as e:
            flash(f"Update Failure: {e}", "danger")
    
    cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
    student = cursor.fetchone()
    conn.close()
    
    if not student:
        flash("Record Missing: Identity not found.", "danger")
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



# --- 2. SUBJECTS MODULE ---
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
        
        try:
            cursor.execute("""
                INSERT INTO subjects (subject_name, department, semester, faculty_id)
                VALUES (%s, %s, %s, %s)
            """, (subject_name, department, semester, faculty_id))
            conn.commit()
            flash("Institution Protocol: New subject successfully registered.", "success")
            return redirect(url_for('admin.view_subjects'))
        except Exception as e:
            flash(f"Synchronization Error: {e}", "danger")
    
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
            flash("Profile Synchronized: Course details updated successfully.", "success")
            return redirect(url_for('admin.view_subjects'))
        except Exception as e:
            flash(f"Update Protocol Error: {e}", "danger")
            
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

# --- 3. FACULTY MODULE ---
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
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        contact_no = request.form.get('contact_no')
        
        try:
            cursor.execute("""
                INSERT INTO faculty (faculty_name, email, department, contact_no)
                VALUES (%s, %s, %s, %s)
            """, (name, email, department, contact_no))
            conn.commit()
            flash("Faculty added successfully!", "success")
            return redirect(url_for('admin.view_faculty'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_faculty.html')

@admin_bp.route('/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
def edit_faculty(faculty_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        contact_no = request.form.get('contact_no')
        
        try:
            cursor.execute("""
                UPDATE faculty 
                SET faculty_name=%s, email=%s, department=%s, contact_no=%s
                WHERE faculty_id=%s
            """, (name, email, department, contact_no, faculty_id))
            conn.commit()
            flash("Faculty details updated successfully!", "success")
            return redirect(url_for('admin.view_faculty'))
        except Exception as e:
            flash(f"Error: {e}", "danger")
            
    cursor.execute("SELECT * FROM faculty WHERE faculty_id = %s", (faculty_id,))
    f_data = cursor.fetchone()
    conn.close()
    return render_template('admin/add_faculty.html', faculty=f_data, edit_mode=True)

@admin_bp.route('/faculty/analytics')
def faculty_analytics():
    filters = {'department': request.args.get('department')}
    from analysis import get_faculty_analytics, generate_faculty_performance_charts
    
    analytics_data = get_faculty_analytics(filters)
    
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

# --- 4. MARKS MODULE ---
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
    chart_values = [round(float(row['avg_marks']), 1) for row in subject_averages]

    # Fetch subjects for filter dropdown
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()
    
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

@admin_bp.route('/add_marks', methods=['GET', 'POST'])
@admin_bp.route('/marks/add', methods=['GET', 'POST'])
def add_marks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT enrollment_no, name FROM students ORDER BY enrollment_no")
    students = cursor.fetchall()
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        enrollment_no = request.form['enrollment_no']
        subject_id = request.form['subject_id']
        i_marks = int(request.form.get('internal_marks', 0))
        v_marks = int(request.form.get('viva_marks', 0))
        e_marks = int(request.form.get('external_marks', 0))
        total = i_marks + v_marks + e_marks

        try:
            # 🛡️ PREVENT / UPDATE DUPLICATE ENTRY (same student + subject)
            cursor.execute("SELECT id FROM marks WHERE enrollment_no = %s AND subject_id = %s", (enrollment_no, subject_id))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE marks 
                    SET internal_marks = %s, viva_marks = %s, external_marks = %s, total_marks = %s 
                    WHERE id = %s
                """, (i_marks, v_marks, e_marks, total, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (enrollment_no, subject_id, i_marks, v_marks, e_marks, total))
            
            conn.commit()
            flash(f"Academic record for {enrollment_no} synchronized successfully!", "success")
            return redirect(url_for('admin.view_marks'))
        except Exception as e:
            conn.rollback()
            flash(f"Data entry failure: {str(e)}", "danger")
    
    conn.close()
    return render_template('admin/add_marks.html', students=students, subjects=subjects)

@admin_bp.route('/edit_marks/<int:marks_id>', methods=['GET', 'POST'])
@admin_bp.route('/marks/edit/<int:marks_id>', methods=['GET', 'POST'])
def edit_marks(marks_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        i_marks = int(request.form.get('internal_marks', 0))
        v_marks = int(request.form.get('viva_marks', 0))
        e_marks = int(request.form.get('external_marks', 0))
        total = i_marks + v_marks + e_marks
        
        try:
            cursor.execute("""
                UPDATE marks 
                SET internal_marks=%s, viva_marks=%s, external_marks=%s, total_marks=%s
                WHERE id=%s
            """, (i_marks, v_marks, e_marks, total, marks_id))
            conn.commit()
            flash("Academic record updated successfully.", "success")
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
        flash("Academic record purged successfully.", "info")
    except Exception as e:
        flash(f"Deletion error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_marks'))

# --- 5. ATTENDANCE MODULE ---
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
    
    conn.close()
    return render_template('admin/view_attendance.html', 
                          attendance_list=attendance_list, 
                          subjects=all_subjects,
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

    # 1. Fetch Subjects for Context
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()
    
    if not subject_id and subjects:
        subject_id = subjects[0]['subject_id']

    # 2. Fetch Aggregated Report Data
    report_data = []
    stats = {'avg_pct': 0, 'low_att': 0}
    
    if subject_id:
        cursor.execute("""
            SELECT s.enrollment_no, s.name,
                   COUNT(a.attendance_id) as total_lectures,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count
            FROM students s
            LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no 
                 AND a.subject_id = %s 
                 AND MONTH(a.date) = %s 
                 AND YEAR(a.date) = %s
            WHERE s.department = %s AND s.semester = %s
            GROUP BY s.enrollment_no
        """, (subject_id, month_val, year_val, department, semester))
        report_data = cursor.fetchall()
        
        if report_data:
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

@admin_bp.route('/attendance/upload-csv', methods=['POST'])
def upload_attendance_csv():
    if 'file' not in request.files:
        flash("System Protocol Alert: No file detected in the buffer.", "danger")
        return redirect(url_for('admin.view_attendance'))
    
    file = request.files['file']
    if file.filename == '':
        flash("Registry Error: No file selected for synchronization.", "danger")
        return redirect(url_for('admin.view_attendance'))

    if not file.filename.endswith('.csv'):
        flash("Buffer Violation: Only CSV files are allowed for institutional uploads.", "warning")
        return redirect(url_for('admin.view_attendance'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 🧪 Cache subjects for name-to-ID mapping to avoid excessive queries
        cursor.execute("SELECT subject_id, LOWER(subject_name) as lower_name FROM subjects")
        subjects_map = {row['lower_name'].strip(): row['subject_id'] for row in cursor.fetchall()}

        # 🧪 Cache students for verification
        cursor.execute("SELECT enrollment_no FROM students")
        students_set = {row['enrollment_no'] for row in cursor.fetchall()}

        from io import StringIO
        import csv
        stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        duplicate_count = 0

        for row in reader:
            # Flexible mapping for student_id/enrollment_no and subject_id/subject_name
            enrollment_no = (row.get('student_id') or row.get('enrollment_no', '')).strip()
            subject_val = (row.get('subject_name') or row.get('subject_id', '')).strip()
            att_date = (row.get('date', '')).strip()
            status = (row.get('status', '')).strip()

            if not enrollment_no or not subject_val or not att_date or not status:
                error_count += 1
                continue

            # Resolve Subject ID if name was provided
            target_sub_id = None
            if str(subject_val).isdigit():
                target_sub_id = int(subject_val)
            else:
                target_sub_id = subjects_map.get(str(subject_val).strip().lower())

            # Validate Student and Subject existence
            if not target_sub_id or enrollment_no not in students_set:
                error_count += 1
                continue

            # Prevent Duplicates
            cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no = %s AND subject_id = %s AND date = %s", 
                         (enrollment_no, target_sub_id, att_date))
            if cursor.fetchone():
                duplicate_count += 1
                continue

            cursor.execute("""
                INSERT INTO attendance (enrollment_no, subject_id, date, status)
                VALUES (%s, %s, %s, %s)
            """, (enrollment_no, target_sub_id, att_date, status))
            success_count += 1

        conn.commit()
        conn.close()

        if success_count > 0:
            flash(f"Synchronization Successful: {success_count} records established. ({error_count} errors, {duplicate_count} duplicates skipped)", "success")
        else:
            flash(f"Synchronization Failed: No valid records were identified. ({error_count} errors, {duplicate_count} duplicates)", "warning")
            
    except Exception as e:
        flash(f"Central Database synchronization failure: {str(e)}", "danger")

    return redirect(url_for('admin.view_attendance'))

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
    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s", (department, semester))
    students = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        att_date = request.form.get('date')
        
        if not subject_id or not att_date:
            flash("Integration Error: Subject and Date credentials are required for bulk synchronization.", "danger")
        else:
            success_count = 0
            for student in students:
                status = request.form.get(f"status_{student['enrollment_no']}")
                if status:
                    # Check for existing record
                    cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no = %s AND subject_id = %s AND date = %s", 
                                 (student['enrollment_no'], subject_id, att_date))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)",
                                     (student['enrollment_no'], subject_id, att_date, status))
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
        
        # ⚠️ VALIDATION (STRICT 🔥)
        if not all([enrollment_no, subject_id, att_date, status]):
            flash("All fields are required!", "danger")
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
        flash("Attendance record permanently deleted.", "success")
    except Exception as e:
        flash(f"Deletion failed: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_attendance'))
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
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/student-report/<enrollment_no>')
def student_report_view(enrollment_no):
    from analysis import get_student_details, get_student_marks, calculate_student_summary
    student = get_student_details(enrollment_no)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('admin.view_students'))
    
    marks_list = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    
    # --- FETCH ATTENDANCE DATA ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Attendance Summary
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
    
    # 2. Detailed Attendance Table (Recent 10)
    cursor.execute("""
        SELECT a.date, a.status, sub.subject_name
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.subject_id
        WHERE a.enrollment_no = %s
        ORDER BY a.date DESC
        LIMIT 10
    """, (enrollment_no,))
    detailed_attendance = cursor.fetchall()
    
    conn.close()
    
    att_info = {
        'total': total_classes,
        'present': present_days,
        'absent': att_summary['absent'] or 0,
        'percent': att_percent
    }
    
    return render_template('admin/student_detail.html', 
                          student=student, 
                          marks_list=marks_list, 
                          summary=summary,
                          attendance=att_info,
                          detailed_attendance=detailed_attendance)

@admin_bp.route('/student-report/<enrollment_no>/download')
def download_student_report(enrollment_no):
    from analysis import generate_student_report_pdf
    from flask import send_file
    
    file_path = generate_student_report_pdf(enrollment_no)
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    flash("Error generating PDF report. Please try again.", "danger")
    return redirect(url_for('admin.student_report_view', enrollment_no=enrollment_no))

@admin_bp.route('/reports')
def view_reports():
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject')
    }
    
    from analysis import get_report_data
    data = get_report_data(filters)
    
    # Get subjects for filter dropdown
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if filters['department'] and filters['department'] != 'All':
        cursor.execute("SELECT DISTINCT subject_name FROM subjects WHERE department = %s", (filters['department'],))
    else:
        cursor.execute("SELECT DISTINCT subject_name FROM subjects")
    subjects = [row['subject_name'] for row in cursor.fetchall()]
    conn.close()
    
    return render_template('admin/view_reports.html', 
                          data=data, 
                          filters=filters, 
                          subjects=subjects)

@admin_bp.route('/reports/export/csv')
def export_csv():
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject')
    }
    from analysis import export_report_csv
    file_path = export_report_csv(filters)
    if file_path:
        from flask import send_file
        return send_file(file_path, as_attachment=True)
    flash("Export failed.", "danger")
    return redirect(url_for('admin.view_reports'))

@admin_bp.route('/reports/export/pdf')
def export_pdf():
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject')
    }
    from analysis import get_report_data, export_report_pdf
    data = get_report_data(filters)
    file_path = export_report_pdf(filters, data)
    if file_path:
        from flask import send_file
        return send_file(file_path, as_attachment=True)
    flash("Export failed.", "danger")
    return redirect(url_for('admin.view_reports'))

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



# --- ADMIN PROFILE MODULE ---
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

# --- 6. FEEDBACK MODULE ---
@admin_bp.route('/feedback')
def view_feedback():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 🎯 Match centralized schema structure
    cursor.execute("""
        SELECT * FROM feedback 
        ORDER BY date DESC
    """)
    feedback_list = cursor.fetchall()
    
    # Simple Status Statistics
    cursor.execute("SELECT COUNT(*) as total FROM feedback")
    total_feedback = cursor.fetchone()['total'] or 0
    
    cursor.execute("SELECT COUNT(*) as pending FROM feedback WHERE admin_reply IS NULL")
    pending_count = cursor.fetchone()['pending'] or 0
    
    conn.close()
    return render_template('admin/view_feedback.html', 
                         feedback=feedback_list, 
                         total=total_feedback,
                         pending=pending_count)

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
        flash("Institutional feedback response successfully recorded.", "success")
    except Exception as e:
        flash(f"Update Failure: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_feedback'))

@admin_bp.route('/feedback/delete/<int:feedback_id>')
def delete_feedback(feedback_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM feedback 
            WHERE feedback_id = %s
        """, (feedback_id,))
        conn.commit()
        flash("Institutional feedback record purged successfully.", "success")
    except Exception as e:
        flash(f"Purge Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_feedback'))

# --- 7. ASYNC API ENDPOINTS ---
@admin_bp.route('/get-students')
def get_students():
    dept = request.args.get('department')
    sem = request.args.get('semester')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s ORDER BY name", (dept, sem))
    students = cursor.fetchall()
    conn.close()
    
    return jsonify({'students': students})

@admin_bp.route('/get-subjects')
def get_subjects():
    """
    Utility: Returns curriculum subjects mapped to specific pedagogical contexts (Dept/Sem).
    Essential for dynamic form synchronization.
    """
    dept = request.args.get('department')
    sem = request.args.get('semester')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT DISTINCT subject_id, subject_name FROM subjects WHERE 1=1"
    params = []
    
    if dept and dept != 'All' and dept != '':
        query += " AND department = %s"
        params.append(dept)
    if sem and sem != 'All' and sem != '':
        query += " AND semester = %s"
        params.append(sem)
        
    query += " ORDER BY subject_name"
    cursor.execute(query, params)
    subjects = cursor.fetchall()
    conn.close()
    
    return jsonify({'subjects': subjects})



