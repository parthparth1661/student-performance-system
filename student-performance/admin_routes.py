from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from analysis import get_dashboard_stats, generate_dashboard_charts, get_performance_overview
from datetime import date
import os
import math

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
    
    # 📋 🧬 STEP 3: GET PERFORMANCE LEDGER (PAGINATED)
    performance_overview, total_records = get_performance_overview(
        filters=filters,
        limit=limit,
        offset=offset
    )
    
    total_pages = math.ceil(total_records / limit)

    # Fetch all subjects for the filter dropdown
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT subject_name FROM subjects ORDER BY subject_name ASC")
    all_subjects = [r['subject_name'] for r in cursor.fetchall()]
    cursor.close()
    conn.close()

    return render_template('admin/admin_dashboard.html', 
                         stats=stats, 
                         filters=filters, 
                         charts=chart_paths,
                         performance_overview=performance_overview,
                         subjects=all_subjects,
                         page=page,
                         total_pages=total_pages,
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
    
    # Fetch subjects for mapping
    cursor.execute("SELECT subject_id, subject_name, department FROM subjects")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        subject_id = request.form.get('subject_id') # Individual mapping
        
        try:
            cursor.execute("""
                INSERT INTO faculty (faculty_name, email, department)
                VALUES (%s, %s, %s)
            """, (name, email, department))
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
    
    # Fetch subjects for mapping
    cursor.execute("SELECT subject_id, subject_name, department FROM subjects")
    subjects = cursor.fetchall()
    
    if request.method == 'POST':
        name = request.form['faculty_name']
        email = request.form['email']
        department = request.form['department']
        subject_id = request.form.get('subject_id')
        
        try:
            cursor.execute("""
                UPDATE faculty 
                SET faculty_name=%s, email=%s, department=%s
                WHERE faculty_id=%s
            """, (name, email, department, faculty_id))
            
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
            AVG(marks_obtained) as avg_marks,
            MAX(marks_obtained) as top_score,
            SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as pass_count
        FROM ({query}) as filtered_marks
    """
    cursor.execute(stats_query, params)
    marks_stats = cursor.fetchone()

    # Calculate total records for pagination
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    query += " ORDER BY m.marks_id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    marks_list = cursor.fetchall()

    # Fetch subjects for filter dropdown
    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    all_subjects = cursor.fetchall()
    
    conn.close()
    return render_template('admin/view_marks.html', 
                          marks_list=marks_list, 
                          subjects=all_subjects,
                          stats=marks_stats,
                          page=page, 
                          total_pages=total_pages,
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
        exam_type = request.form['exam_type']
        marks_obtained = request.form['marks_obtained']
        total_marks = request.form.get('total_marks', 100)
        
        # ⚠️ VALIDATION (STRICT 🔥)
        if not all([enrollment_no, subject_id, exam_type, marks_obtained]):
            flash("All fields are mandatory!", "danger")
        else:
            try:
                marks_obtained = float(marks_obtained)
                total_marks = float(total_marks)
                
                if marks_obtained < 0 or marks_obtained > 100:
                    flash("Validation Error: Marks must be between 0 and 100.", "danger")
                elif marks_obtained > total_marks:
                    flash(f"Sanity Check Failed: Obtained marks ({marks_obtained}) cannot exceed total marks ({total_marks})!", "danger")
                else:
                    # 🛡️ PREVENT DUPLICATE ENTRY (same student + subject + exam)
                    cursor.execute("""
                        SELECT * FROM marks 
                        WHERE enrollment_no = %s AND subject_id = %s AND exam_type = %s
                    """, (enrollment_no, subject_id, exam_type))
                    
                    if cursor.fetchone():
                        flash(f"Duplicate Entry Warning: Record already exists for Student {enrollment_no} in this subject and exam type.", "warning")
                    else:
                        # Auto-calculate status
                        status = 'PASS' if (marks_obtained / total_marks) * 100 >= 40 else 'FAIL'
                        
                        cursor.execute("""
                            INSERT INTO marks (enrollment_no, subject_id, exam_type, marks_obtained, total_marks, status)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (enrollment_no, subject_id, exam_type, marks_obtained, total_marks, status))
                        conn.commit()
                        flash(f"Result for {enrollment_no} registered successfully!", "success")
                        return redirect(url_for('admin.view_marks'))
            except ValueError:
                flash("Invalid numeric value for marks.", "danger")
            except Exception as e:
                flash(f"Database Error: {e}", "danger")
    
    conn.close()
    return render_template('admin/add_marks.html', students=students, subjects=subjects)

@admin_bp.route('/edit_marks/<int:marks_id>', methods=['GET', 'POST'])
@admin_bp.route('/marks/edit/<int:marks_id>', methods=['GET', 'POST'])
def edit_marks(marks_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        marks_obtained = float(request.form['marks_obtained'])
        total_marks = float(request.form.get('total_marks', 100))
        exam_type = request.form['exam_type']
        
        if marks_obtained < 0 or marks_obtained > 100:
            flash("Validation Error: Marks must be between 0 and 100.", "danger")
        elif marks_obtained > total_marks:
            flash("Validation Error: Marks obtained exceeds total possible marks.", "danger")
        else:
            status = 'PASS' if (marks_obtained / total_marks) * 100 >= 40 else 'FAIL'
            try:
                cursor.execute("""
                    UPDATE marks 
                    SET marks_obtained=%s, total_marks=%s, exam_type=%s, status=%s
                    WHERE marks_id=%s
                """, (marks_obtained, total_marks, exam_type, status, marks_id))
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
        WHERE m.marks_id = %s
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
        cursor.execute("DELETE FROM marks WHERE marks_id = %s", (marks_id,))
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
    
    conn.close()
    return render_template('admin/view_attendance.html', 
                          attendance_list=attendance_list, 
                          subjects=all_subjects,
                          stats=att_stats,
                          low_att_count=low_att_count,
                          low_att_ids=low_att_ids,
                          page=page, 
                          total_pages=total_pages,
                          filters={
                              'enrollment': enrollment, 
                              'department': department,
                              'semester': semester,
                              'subject_id': subject_id,
                              'status': status_filter,
                              'date': date_filter
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
    from analysis import get_student_details, get_student_marks, calculate_student_summary, generate_student_charts_new
    student = get_student_details(enrollment_no)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('admin.view_students'))
    
    marks_list = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    generate_student_charts_new(enrollment_no)
    
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
    
    from analysis import get_report_data, generate_report_charts
    data = get_report_data(filters)
    generate_report_charts(data)
    
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
