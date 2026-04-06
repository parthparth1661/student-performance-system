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
    from analysis import get_dashboard_stats, get_performance_overview
    
    # NEW CLEAN FILTERING (STEP 3) 🎯
    department = request.args.get('department')
    semester = request.args.get('semester')
    
    # NEW DYNAMIC DATA FETCH 🎯
    overview_data = get_performance_overview(department, semester)
    stats = get_dashboard_stats() # Still needed for basic counts
    
    return render_template('admin/admin_dashboard.html', 
                           stats=stats, 
                           total_students=stats['total_students'],
                           total_subjects=stats['total_subjects'],
                           avg_marks=stats['avg_marks'],
                           attendance_percentage=stats['attendance_percentage'],
                           performance_overview=overview_data,
                           filters={'department': department, 'semester': semester})

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
    from analysis import export_admin_excel
    file_path = export_admin_excel(dept, sem)
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
