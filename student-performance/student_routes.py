"""
SPDA Student Intelligence Portal
------------------------------------
Orchestrates the student-facing experience including academic performance 
visualization, attendance monitoring, and institutional feedback submission.
"""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
import analysis

student_bp = Blueprint('student', __name__, url_prefix='/student')

# BRIDGE SECURITY: PROTECT ALL STUDENT ROUTES
@student_bp.before_request
def student_auth_guard():
    """Ensures all student-facing routes are protected by institutional identity verification."""
    public_endpoints = ['student.login', 'static']
    if request.endpoint in public_endpoints:
        return
    
    if 'student_id' not in session:
        return redirect(url_for('student.login'))

# --- 1. IDENTITY & ACCESS CONTROL ---

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles student authentication via institutional enrollment credentials.
    Enforces mandatory password rotation for newly provisioned accounts.
    """
    if 'student_id' in session:
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        enrollment_no = request.form.get('enrollment_no')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
        student = cursor.fetchone()
        conn.close()

        if student and check_password_hash(student['password_hash'], password):
            session['student_id'] = student['enrollment_no']
            session['student_name'] = student['name']
            session['student_dept'] = student['department']
            
            # Security Protocol: Enforce password change if account is using default enrollment as password
            if not student['is_password_changed']:
                flash("Security Alert: Initial identity detected. Please update your password.", "warning")
                return redirect(url_for('student.change_password'))
                
            flash(f"Access Granted: Welcome {student['name']}.", "success")
            return redirect(url_for('student.dashboard'))
        else:
            flash("Authentication Failed: Invalid enrollment number or password.", "danger")
            
    return render_template('student/login.html')

@student_bp.route('/logout')
def logout():
    """Terminates institutional session and clears security tokens."""
    session.clear()
    flash("Session terminated successfully.", "info")
    return redirect(url_for('student.login'))


# --- 2. ACADEMIC INTELLIGENCE NEXUS ---

@student_bp.route('/dashboard')
def dashboard():
    """
    Student Command Center.
    Visualizes private performance trends, attendance status, and academic KPIs.
    """
    enrollment_no = session['student_id']
    
    # Fetch performance data via enrollment-locked analysis
    student_info = analysis.get_student_details(enrollment_no)
    marks_data = analysis.get_student_marks(enrollment_no)
    
    # Calculate Attendance Percentage
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COALESCE(COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 0) as attendance
        FROM attendance WHERE enrollment_no = %s
    """, (enrollment_no,))
    attn_data = cursor.fetchone()
    
    # Fetch Feedback Status
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN admin_reply IS NULL THEN 1 END) as pending,
            COUNT(CASE WHEN admin_reply IS NOT NULL THEN 1 END) as resolved
        FROM feedback WHERE student_id = %s
    """, (enrollment_no,))
    fb_stats = cursor.fetchone()
    conn.close()
    
    return render_template('student/student_dashboard.html', 
                           student=student_info, 
                           marks_list=marks_data, 
                           attendance_pct=round(attn_data['attendance'] or 0, 1),
                           fb_stats=fb_stats,
                           subjects=[m['subject'] for m in marks_data],
                           marks=[m['total'] for m in marks_data])

@student_bp.route('/performance')
def performance():
    """Extended academic ledger: High-density breakdown of component-wise outcomes."""
    enrollment_no = session['student_id']
    student_info = analysis.get_student_details(enrollment_no)
    marks_data = analysis.get_student_marks(enrollment_no)
    
    return render_template('student/performance.html', 
                           student=student_info, 
                           marks_list=marks_data)


# --- 3. INSTITUTIONAL FEEDBACK ---

@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback():
    """Institutional Feedback Channel: Allows students to contribute pedagogical insights."""
    enrollment_no = session['student_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        subject = request.form.get('subject')
        comment = request.form.get('message')
        faculty = request.form.get('faculty', 'General')
        rating = request.form.get('rating', 5)
        
        if comment and subject:
            cursor.execute("SELECT name, department, semester FROM students WHERE enrollment_no = %s", (enrollment_no,))
            student = cursor.fetchone()
            
            if student:
                cursor.execute("""
                    INSERT INTO feedback (student_id, student_name, department, semester, subject, faculty, rating, comment) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (enrollment_no, student['name'], student['department'], student['semester'], subject, faculty, rating, comment))
                conn.commit()
                flash("Contribution Received: Thank you for your institutional feedback.", "success")
                return redirect(url_for('student.feedback'))
    
    cursor.execute("SELECT * FROM feedback WHERE student_id = %s ORDER BY date DESC", (enrollment_no,))
    history = cursor.fetchall()
    
    cursor.execute("SELECT * FROM subjects")
    all_subjects = cursor.fetchall()
    
    student_info = analysis.get_student_details(enrollment_no)
    conn.close()
    return render_template('student/feedback.html', 
                           student=student_info, 
                           history=history, 
                           subjects=all_subjects)


# --- 4. SECURITY PROTOCOL ---

@student_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """Private Security Module: Enables autonomous credential rotation."""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("Security Alert: Passwords do not match.", "danger")
            return redirect(url_for('student.change_password'))
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT password_hash FROM students WHERE enrollment_no = %s", (session['student_id'],))
        student = cursor.fetchone()
        
        if student and check_password_hash(student['password_hash'], current_password):
            new_hash = generate_password_hash(new_password)
            cursor.execute("""
                UPDATE students 
                SET password_hash = %s, is_password_changed = TRUE 
                WHERE enrollment_no = %s
            """, (new_hash, session['student_id']))
            conn.commit()
            conn.close()
            flash("Identity Profile Hardened: New credentials active.", "success")
            return redirect(url_for('student.dashboard'))
        else:
            conn.close()
            flash("Authorization Denied: Current credentials incorrect.", "danger")
            
    return render_template('student/change_password.html')
