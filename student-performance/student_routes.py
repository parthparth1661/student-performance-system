from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import analysis

student_bp = Blueprint('student', __name__, url_prefix='/student')

# 🛡️ BRIDGE SECURITY: PROTECT ALL STUDENT ROUTES
@student_bp.before_request
def student_auth_guard():
    # Public routes that don't need authentication
    public_endpoints = ['student.login', 'static']
    if request.endpoint in public_endpoints:
        return
    
    # Check session
    if 'student_id' not in session:
        return redirect(url_for('student.login'))

# 🔑 AUTHENTICATION UNIT: LOGIN
@student_bp.route('/login', methods=['GET', 'POST'])
def login():
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
            # Establish secure session
            session['student_id'] = student['enrollment_no']
            session['student_name'] = student['name']
            session['student_dept'] = student['department']
            session['is_password_changed'] = bool(student['is_password_changed'])
            
            # 🔄 FORCED ROTATION: Redirect if using default password
            if not student['is_password_changed']:
                flash("Initial access detected. Security protocol requires password rotation.", "warning")
                return redirect(url_for('student.change_password'))
                
            return redirect(url_for('student.dashboard'))
        else:
            flash("Invalid institutional credentials. Please verify your identity.", "danger")
            
    return render_template('student/login.html')

# 📊 ANALYTICAL HUB: DASHBOARD
@student_bp.route('/dashboard')
def dashboard():
    enrollment_no = session['student_id']
    
    # Fetch performance data via enrollment-locked analysis
    student_info = analysis.get_student_details(enrollment_no)
    marks_data = analysis.get_student_marks(enrollment_no) 
    perf_summary = analysis.calculate_student_summary(enrollment_no)
    
    # Calculate Attendance Percentage for the UI
    conn = analysis.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            (COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) as attendance
        FROM attendance WHERE enrollment_no = %s
    """, (enrollment_no,))
    attn_data = cursor.fetchone()
    perf_summary['attendance_percentage'] = round(attn_data['attendance'] or 0, 2)
    conn.close()
    
    # Generate dynamic performance visualizations
    analysis.generate_student_charts_new(enrollment_no)
    
    return render_template('student/student_dashboard.html', 
                           student=student_info, 
                           marks_list=marks_data, 
                           summary=perf_summary,
                           subjects=[m['subject'] for m in marks_data],
                           marks=[m['total'] for m in marks_data])

# 📈 ACADEMIC TRACKING: PERFORMANCE
@student_bp.route('/performance')
def performance():
    enrollment_no = session['student_id']
    student_info = analysis.get_student_details(enrollment_no)
    marks_data = analysis.get_student_marks(enrollment_no)
    perf_summary = analysis.calculate_student_summary(enrollment_no)
    
    return render_template('student/performance.html', 
                           student=student_info, 
                           marks_list=marks_data, 
                           summary=perf_summary,
                           subjects=[m['subject'] for m in marks_data],
                           marks=[m['total'] for m in marks_data])

# 👤 IDENTITY SECTOR: PROFILE
@student_bp.route('/profile')
def profile():
    enrollment_no = session['student_id']
    student_info = analysis.get_student_details(enrollment_no)
    return render_template('student/profile.html', student=student_info)

# 🔐 SECURITY PROTOCOL: CHANGE PASSWORD
@student_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash("New credentials do not match.", "danger")
            return redirect(url_for('student.change_password'))
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Verify identity again for security
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
            
            session['is_password_changed'] = True
            flash("Credentials updated successfully. Security protocol verified.", "success")
            return redirect(url_for('student.dashboard'))
        else:
            conn.close()
            flash("Identity verification failed. Current password incorrect.", "danger")
            
    return render_template('student/change_password.html')

# 💬 COMMUNICATION: FEEDBACK
@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        message = request.form.get('message')
        enrollment_no = session['student_id']
        
        if message:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO feedback (enrollment_no, message) VALUES (%s, %s)", (enrollment_no, message))
            conn.commit()
            conn.close()
            flash("Feedback submitted successfully. Institutional improvement in progress.", "success")
            return redirect(url_for('student.dashboard'))
        
    enrollment_no = session['student_id']
    student_info = analysis.get_student_details(enrollment_no)
    return render_template('student/feedback.html', student=student_info)

# 🚪 SESSION TERMINATION: LOGOUT
@student_bp.route('/logout')
def logout():
    session.clear()
    flash("Session terminated successfully.", "info")
    return redirect(url_for('student.login'))
