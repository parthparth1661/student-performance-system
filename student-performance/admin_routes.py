from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from functools import wraps
from werkzeug.security import check_password_hash
from db import get_db_connection
from analysis import (
    get_dashboard_stats, 
    process_csv, 
    fetch_student_by_roll, 
    fetch_student_marks, 
    calculate_student_stats, 
    generate_student_charts,
    get_attendance_summary,
    clear_charts,
    get_low_attendance_students,
    get_weak_students_external,
    export_admin_excel
)
from datetime import date
import os
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)


# --- Authentication Protection (Rule B & C) ---
@admin_bp.before_request
def check_admin_login():
    # Allow login and logout to be accessed without login
    if request.endpoint in ['admin.login', 'admin.logout', 'admin.static']: 
        return
    
    # Check if admin is logged in
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Rule C: Redirect to dashboard if already logged in
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('admin/admin_login.html')
            
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cursor.fetchone()
            
            if admin and check_password_hash(admin['password_hash'], password):
                session['admin_logged_in'] = True
                session['admin_id'] = admin['admin_id']
                session['admin_username'] = admin['username']
                flash(f"Welcome back, {username}!", "success")
                return redirect(url_for('admin.dashboard'))
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            flash(f"Login error: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()
            
    return render_template('admin/admin_login.html')

@admin_bp.route('/logout')
def logout():
    # Rule D: Clear session fully and redirect
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('admin.login'))

# --- Profile Management ---
@admin_bp.route('/profile')

def profile():
    conn = get_db_connection()
    if not conn:
        flash("Database connection error!", "danger")
        return redirect(url_for('admin.dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admins WHERE admin_id = %s", (session['admin_id'],))
    admin = cursor.fetchone()
    conn.close()
    
    return render_template('admin/profile.html', admin=admin)

@admin_bp.route('/profile/update', methods=['POST'])

def update_profile():
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection error!", "danger")
        return redirect(url_for('admin.dashboard'))
        
    try:
        cursor = conn.cursor()
        
        cursor.execute("UPDATE admins SET full_name = %s, email = %s WHERE admin_id = %s", 
                       (full_name, email, session['admin_id']))
        conn.commit()
        
        flash("Profile updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating profile: {str(e)}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('admin.profile'))

@admin_bp.route('/change_password', methods=['GET', 'POST'])

def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("New passwords do not match!", "danger")
            return redirect(url_for('admin.change_password'))
            
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return redirect(url_for('admin.dashboard'))
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT password_hash FROM admins WHERE admin_id = %s", (session['admin_id'],))
            admin = cursor.fetchone()
            
            if admin and check_password_hash(admin['password_hash'], current_password):
                from werkzeug.security import generate_password_hash
                hashed_password = generate_password_hash(new_password)
                
                cursor.execute("UPDATE admins SET password_hash = %s WHERE admin_id = %s", 
                               (hashed_password, session['admin_id']))
                conn.commit()
                flash("Password changed successfully!", "success")
                return redirect(url_for('admin.profile'))
            else:
                flash("Incorrect current password!", "danger")
        except Exception as e:
            flash(f"Error changing password: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('admin/change_password.html')

# --- Dashboard ---
@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    department = request.args.get('department', 'All')
    semester = request.args.get('semester', 'All')
    exam_type = request.args.get('exam_type', 'All')
    
    stats = get_dashboard_stats(department, semester, exam_type)
    
    # 8. Get Low Attendance and Weak Students for Warnings
    low_attendance = get_low_attendance_students(75)
    weak_students = get_weak_students_external(35)
    
    # If stats is empty (error case), provide defaults
    if not stats:
        stats = {
            'total_students': 0, 'total_marks': 0,
            'pass_count': 0, 'fail_count': 0,
            'subject_avg': [], 'top_students': [], 'weak_students': []
        }
        
    return render_template('admin/admin_dashboard.html', 
                           stats=stats, 
                           low_attendance=low_attendance,
                           weak_students_alert=weak_students,
                           filters=request.args)

@admin_bp.route('/export_excel')
def export_excel():
    department = request.args.get('department', 'All')
    semester = request.args.get('semester', 'All')
    
    file_path = export_admin_excel(department, semester)
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name='admin_report.xlsx')
    else:
        flash("Could not generate Excel report.", "danger")
        return redirect(url_for('admin.dashboard'))

# --- Student Management ---
@admin_bp.route('/students')
def view_students():
    roll_no = request.args.get('roll_no', '').strip()
    name = request.args.get('name', '').strip()
    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return render_template('admin/view_students.html', students=[], departments=[], semesters=[], filters=request.args)
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
    if roll_no:
        query += " AND roll_no LIKE %s"
        params.append(f"%{roll_no}%")
    if name:
        query += " AND name LIKE %s"
        params.append(f"%{name}%")
    if department:
        query += " AND department = %s"
        params.append(department)
    if semester:
        query += " AND semester = %s"
        params.append(semester)
        
    cursor.execute(query, params)
    students = cursor.fetchall()
    
    # Get distinct departments and semesters for filters
    cursor.execute("SELECT DISTINCT department FROM students WHERE department IS NOT NULL")
    departments = [row['department'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT semester FROM students WHERE semester IS NOT NULL")
    semesters = [row['semester'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('admin/view_students.html', 
                          students=students, 
                          departments=departments, 
                          semesters=semesters,
                          filters=request.args)

@admin_bp.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection failed!", "danger")
            return redirect(url_for('admin.dashboard'))
        try:
            from werkzeug.security import generate_password_hash
            default_password = roll_no + "@123"
            password_hash = generate_password_hash(default_password)
            
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO students (roll_no, name, email, department, semester, password_hash, is_password_changed)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
            """, (roll_no, name, email, department, semester, password_hash))
            conn.commit()
            flash(f"Student added! Default password: {default_password}", "success")
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('admin/add_student.html')

@admin_bp.route('/students/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for('admin.dashboard'))
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        semester = request.form['semester']

        try:
            cursor.execute("""
                UPDATE students
                SET roll_no=%s, name=%s, email=%s, department=%s, semester=%s
                WHERE student_id=%s
            """, (roll_no, name, email, department, semester, id))
            conn.commit()
            flash("Student updated successfully!", "success")
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    cursor.execute("SELECT * FROM students WHERE student_id = %s", (id,))
    student = cursor.fetchone()
    conn.close()

    if not student:
        flash("Student not found!", "warning")
        return redirect(url_for('admin.view_students'))

    return render_template('admin/edit_student.html', student=student)

@admin_bp.route('/students/delete/<int:id>')
def delete_student(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for('admin.dashboard'))
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE student_id = %s", (id,))
        conn.commit()
        flash("Student deleted successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))

# --- Helper Route for AJAX ---
@admin_bp.route('/get_student_dept/<roll_no>')
def get_student_dept(roll_no):
    from db import get_db_connection
    conn = get_db_connection()
    if not conn:
        return {"error": "DB Connection failed"}, 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT department FROM students WHERE roll_no = %s", (roll_no,))
    student = cursor.fetchone()
    conn.close()
    if student:
        return student
    return {"error": "Student not found"}, 404

# --- Marks Management ---
@admin_bp.route('/marks')
def view_marks():
    roll_no = request.args.get('roll_no', '')
    subject = request.args.get('subject', '')
    min_marks = request.args.get('min_marks', '')
    max_marks = request.args.get('max_marks', '')
    exam_type = request.args.get('exam_type', '')

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return render_template('admin/view_marks.html', marks_list=[], subjects=["Python","Java","DBMS","DSA","OS","AI"], filters=request.args)
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT m.*, s.roll_no, s.name
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        WHERE 1=1
    """
    params = []

    if roll_no:
        query += " AND s.roll_no = %s"
        params.append(roll_no)
    if subject:
        query += " AND m.subject LIKE %s"
        params.append(f"%{subject}%")
    if min_marks:
        query += " AND m.marks >= %s"
        params.append(min_marks)
    if max_marks:
        query += " AND m.marks <= %s"
        params.append(max_marks)
    if exam_type:
        query += " AND m.exam_type = %s"
        params.append(exam_type)

    cursor.execute(query, params)
    marks_list = cursor.fetchall()

    cursor.close()
    conn.close()

    subjects = ["Python","Java","DBMS","DSA","OS","AI"]
    return render_template('admin/view_marks.html', marks_list=marks_list, subjects=subjects, filters=request.args)

@admin_bp.route('/marks/add', methods=['GET', 'POST'])
def add_marks():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        subject = request.form['subject']
        marks = request.form['marks']
        exam_type = request.form['exam_type']
        exam_date = request.form['exam_date']

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed!", "danger")
            return redirect(url_for('admin.dashboard'))
        cursor = conn.cursor(dictionary=True)

        # Find student_id and department by roll_no
        cursor.execute("SELECT student_id, department FROM students WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()

        if not student:
            flash("Student with this Roll No does not exist!", "danger")
            conn.close()
        elif exam_type == 'Practical' and student['department'] == 'MBA':
            flash("Practical exams are not allowed for MBA department!", "danger")
            conn.close()
        else:
            try:
                cursor.execute("""
                    INSERT INTO marks (student_id, subject, marks, exam_type, exam_date)
                    VALUES (%s, %s, %s, %s, %s)
                """, (student['student_id'], subject, marks, exam_type, exam_date))
                conn.commit()
                flash("Marks added successfully!", "success")
                return redirect(url_for('admin.dashboard'))
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")
            finally:
                conn.close()

    subjects = ["Python","Java","DBMS","DSA","OS","AI"]
    return render_template('admin/add_marks.html', subjects=subjects)

@admin_bp.route('/marks/edit/<int:id>', methods=['GET', 'POST'])
def edit_marks(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for('admin.dashboard'))
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        subject = request.form['subject']
        marks = request.form['marks']
        exam_type = request.form['exam_type']
        exam_date = request.form['exam_date']

        # Get department to validate practical rule
        cursor.execute("""
            SELECT s.department FROM students s
            JOIN marks m ON s.student_id = m.student_id
            WHERE m.marks_id = %s
        """, (id,))
        dept_row = cursor.fetchone()
        
        if dept_row and exam_type == 'Practical' and dept_row['department'] == 'MBA':
            flash("Practical exams are not allowed for MBA department!", "danger")
        else:
            try:
                cursor.execute("""
                    UPDATE marks
                    SET subject=%s, marks=%s, exam_type=%s, exam_date=%s
                    WHERE marks_id=%s
                """, (subject, marks, exam_type, exam_date, id))
                conn.commit()
                flash("Marks updated successfully!", "success")
                return redirect(url_for('admin.dashboard'))
            except Exception as e:
                flash(f"Error: {str(e)}", "danger")

    cursor.execute("""
        SELECT m.*, s.roll_no, s.name, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        WHERE m.marks_id = %s
    """, (id,))
    mark = cursor.fetchone()
    conn.close()

    if not mark:
        flash("Record not found!", "warning")
        return redirect(url_for('admin.view_marks'))

    subjects = ["Python","Java","DBMS","DSA","OS","AI"]
    return render_template('admin/edit_marks.html', mark=mark, subjects=subjects)

@admin_bp.route('/marks/delete/<int:id>')
def delete_marks(id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for('admin.dashboard'))
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM marks WHERE marks_id = %s", (id,))
        conn.commit()
        flash("Record deleted successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))

# --- CSV Upload ---
@admin_bp.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash("No selected file", "danger")
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            upload_path = os.path.join('static', filename)
            file.save(upload_path)
            
            success, message = process_csv(upload_path)
            # Remove file after processing
            if os.path.exists(upload_path):
                os.remove(upload_path)
                
            if success:
                flash(message, "success")
                return redirect(url_for('admin.dashboard'))
            else:
                flash(message, "danger")
        else:
            flash("Only CSV files are allowed.", "danger")
            
    return render_template('admin/upload_csv.html')

# --- Attendance Management ---

@admin_bp.route('/attendance/mark', methods=['GET', 'POST'])
def mark_attendance():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return redirect(url_for('admin.dashboard'))
    
    cursor = conn.cursor(dictionary=True)
    
    # Default to today if no date provided
    attendance_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    
    if request.method == 'POST':
        attendance_date = request.form['attendance_date']
        student_ids = request.form.getlist('student_id')
        
        try:
            for sid in student_ids:
                status = request.form.get(f'status_{sid}')
                remarks = request.form.get(f'remarks_{sid}', '')
                
                # Upsert logic for attendance
                cursor.execute("""
                    INSERT INTO attendance (student_id, attendance_date, status, remarks)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE status = %s, remarks = %s
                """, (sid, attendance_date, status, remarks, status, remarks))
            
            conn.commit()
            flash(f"Attendance marked successfully for {attendance_date}!", "success")
            return redirect(url_for('admin.mark_attendance', date=attendance_date))
        except Exception as e:
            flash(f"Error marking attendance: {str(e)}", "danger")
            conn.rollback()

    # Get all students to display in the marking form
    cursor.execute("SELECT student_id, roll_no, name, department, semester FROM students ORDER BY roll_no")
    students = cursor.fetchall()
    
    # Get existing attendance for this date to pre-fill the form
    cursor.execute("SELECT student_id, status, remarks FROM attendance WHERE attendance_date = %s", (attendance_date,))
    existing_attendance = {row['student_id']: row for row in cursor.fetchall()}
    
    # Merge existing data into students list
    for s in students:
        s['status'] = existing_attendance.get(s['student_id'], {}).get('status', 'Present')
        s['remarks'] = existing_attendance.get(s['student_id'], {}).get('remarks', '')

    cursor.close()
    conn.close()
    
    return render_template('admin/attendance_mark.html', students=students, attendance_date=attendance_date)

@admin_bp.route('/attendance')
def view_attendance():
    roll_no = request.args.get('roll_no', '')
    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    status = request.args.get('status', '')

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed!", "danger")
        return render_template('admin/attendance_view.html', records=[], filters=request.args)
    
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT a.*, s.roll_no, s.name, s.department, s.semester
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE 1=1
    """
    params = []

    if roll_no:
        query += " AND s.roll_no = %s"
        params.append(roll_no)
    if department:
        query += " AND s.department = %s"
        params.append(department)
    if semester:
        query += " AND s.semester = %s"
        params.append(semester)
    if from_date:
        query += " AND a.attendance_date >= %s"
        params.append(from_date)
    if to_date:
        query += " AND a.attendance_date <= %s"
        params.append(to_date)
    if status:
        query += " AND a.status = %s"
        params.append(status)

    query += " ORDER BY a.attendance_date DESC, s.roll_no"
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    # Get departments/semesters for filters
    cursor.execute("SELECT DISTINCT department FROM students WHERE department IS NOT NULL")
    departments = [r['department'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT semester FROM students WHERE semester IS NOT NULL")
    semesters = [r['semester'] for r in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return render_template('admin/attendance_view.html', 
                           records=records, 
                           departments=departments, 
                           semesters=semesters, 
                           filters=request.args)

@admin_bp.route('/attendance/upload', methods=['GET', 'POST'])
def upload_attendance():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch Depts/Sems for Dropdown
    cursor.execute("SELECT DISTINCT department FROM students")
    departments = [r['department'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT semester FROM students")
    semesters = [r['semester'] for r in cursor.fetchall()]
    conn.close()

    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)
            
        file = request.files['file']
        department = request.form.get('department')
        semester = request.form.get('semester')
        
        if file.filename == '' or not department or not semester:
            flash("Please select file, department and semester", "danger")
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            upload_path = os.path.join('static', filename)
            file.save(upload_path)
            
            # Pass dept/sem to process_csv for validation
            success, message = process_csv(upload_path, department, semester)
            
            if os.path.exists(upload_path):
                os.remove(upload_path)
                
            if success:
                flash(message, "success")
                return redirect(url_for('admin.view_attendance', department=department, semester=semester))
            else:
                flash(message, "danger")
        else:
            flash("Only CSV files are allowed.", "danger")
            
    return render_template('admin/attendance_upload.html', departments=departments, semesters=semesters)

@admin_bp.route('/calendar', methods=['GET', 'POST'])
def academic_calendar():
    conn = get_db_connection()
    
    if request.method == 'POST':
        department = request.form.get('department')
        semester = request.form.get('semester')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO academic_calendar (department, semester, start_date, end_date)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE start_date=%s, end_date=%s
            """, (department, semester, start_date, end_date, start_date, end_date))
            conn.commit()
            flash(f"Calendar updated for {department} - {semester}", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
            
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM academic_calendar ORDER BY department, semester")
    terms = cursor.fetchall()
    
    # For Dropdowns
    cursor.execute("SELECT DISTINCT department FROM students")
    departments = [r['department'] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT semester FROM students")
    semesters = [r['semester'] for r in cursor.fetchall()]
    
    conn.close()
    return render_template('admin/calendar.html', terms=terms, departments=departments, semesters=semesters)

@admin_bp.route('/attendance/summary')
def attendance_summary():
    summary = get_attendance_summary()
    return render_template('admin/attendance_summary.html', summary=summary)

# --- Student Performance Report ---
@admin_bp.route('/student_report', methods=['GET'])
def student_report_search():
    roll_no = request.args.get('roll_no', '')
    student = None
    if roll_no:
        student = fetch_student_by_roll(roll_no)
        if not student:
            flash(f"No student found with Roll No: {roll_no}", "warning")
            
    return render_template('admin/student_report_search.html', student=student, roll_no=roll_no)

@admin_bp.route('/student_report/<roll_no>')
def student_report_view(roll_no):
    student = fetch_student_by_roll(roll_no)
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for('admin.student_report_search'))
    
    marks_list = fetch_student_marks(student['student_id'])
    stats = calculate_student_stats(marks_list)
    
    if marks_list:
        generate_student_charts(roll_no, student['name'], marks_list)
        
    return render_template('admin/student_report_view.html', 
                           student=student, 
                           marks_list=marks_list, 
                           stats=stats)

@admin_bp.route('/reset_data', methods=['GET', 'POST'])
def reset_data():
    if request.method == 'POST':
        confirmation = request.form.get('confirmation_code', '').strip()
        
        if confirmation != 'RESET':
            flash("Invalid confirmation code! Please type 'RESET' exactly.", "danger")
            return redirect(url_for('admin.reset_data'))

        conn = get_db_connection()
        if not conn:
            flash("Database connection failed!", "danger")
            return redirect(url_for('admin.dashboard'))
        
        cursor = None
        try:
            cursor = conn.cursor()
            # Safe reset sequence
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("TRUNCATE TABLE attendance;")
            cursor.execute("TRUNCATE TABLE marks;")
            cursor.execute("TRUNCATE TABLE students;")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            conn.commit()
            
            # Clear stale charts from static folder
            clear_charts()
            
            flash("All data has been successfully reset. Start by adding new students.", "success")
            return redirect(url_for('admin.dashboard'))
        except Exception as e:
            flash(f"Error resetting data: {str(e)}", "danger")
        finally:
            if cursor:
                cursor.close()
            conn.close()
            
    return render_template('admin/reset_data.html')
