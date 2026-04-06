from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, session
from analysis import (
    get_student_details,
    get_student_marks,
    calculate_student_summary,
    generate_student_charts_new,
    export_student_report_excel
)
from db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import os

student_bp = Blueprint('student', __name__, url_prefix='/student')

# --- Middleware for Login Protection ---
@student_bp.before_request
def check_student_login():
    # Allow login, static, and change_password without full dashboard access
    allowed = ['student.login', 'student.change_password', 'student.logout', 'study_static']
    if request.endpoint in allowed:
        return
        
    # Check if student is logged in
    if not session.get('student_logged_in'):
        return redirect(url_for('student.login'))
        
    # Force password change if needed
    # Note: We need to allow the change_password route itself, which is handled above
    if not session.get('is_password_changed') and request.endpoint != 'student.change_password':
        flash("Please change your password to continue.", "warning")
        return redirect(url_for('student.change_password'))

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('student_logged_in'):
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        enrollment_no = request.form.get('roll_no') # using 'roll_no' from form for compatibility
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('student/login.html')
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
        student = cursor.fetchone()
        conn.close()
        
        if student and student['password_hash'] and check_password_hash(student['password_hash'], password):
            session['student_logged_in'] = True
            session['student_enrollment_no'] = student['enrollment_no']
            session['student_name'] = student['name']
            session['is_password_changed'] = bool(student['is_password_changed'])
            
            if not student['is_password_changed']:
                return redirect(url_for('student.change_password'))
                
            return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid Enrollment No or Password.", "danger")
            
    return render_template('student/login.html')

@student_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if not session.get('student_logged_in'):
        return redirect(url_for('student.login'))
        
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('student.change_password'))
            
        conn = get_db_connection()
        try:
            hashed_pw = generate_password_hash(new_password)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE students 
                SET password_hash=%s, is_password_changed=TRUE 
                WHERE enrollment_no=%s
            """, (hashed_pw, session['student_enrollment_no']))
            conn.commit()
            
            session['is_password_changed'] = True
            flash("Password changed successfully!", "success")
            return redirect(url_for('student.dashboard'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            conn.close()
            
    return render_template('student/change_password.html')

@student_bp.route('/dashboard')
def dashboard():
    enrollment_no = session['student_enrollment_no']
    student = get_student_details(enrollment_no)
    marks_list = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    
    generate_student_charts_new(enrollment_no)
    
    return render_template('student/student_dashboard.html', 
                           student=student, 
                           marks_list=marks_list, 
                           summary=summary)

@student_bp.route('/report/download')
def download_report():
    enrollment_no = session['student_enrollment_no']
    file_path = export_student_report_excel(enrollment_no)
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=f'student_{enrollment_no}_report.xlsx')
    else:
        flash("Could not generate Excel report.", "danger")
        return redirect(url_for('student.dashboard'))
