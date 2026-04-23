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
    # Fetch Feedback Status Counts
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN admin_reply IS NULL THEN 1 END) as pending,
            COUNT(CASE WHEN admin_reply IS NOT NULL THEN 1 END) as resolved
        FROM feedback WHERE student_id = %s
    """, (enrollment_no,))
    fb_stats = cursor.fetchone()
    
    # 🛰️ SUBJECT-WISE ATTENDANCE ANALYSIS
    cursor.execute("""
        SELECT sub.subject_name,
               COALESCE((SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(a.attendance_id), 0)), 0) as attendance_pct
        FROM subjects sub
        LEFT JOIN attendance a ON sub.subject_id = a.subject_id AND a.enrollment_no = %s
        WHERE sub.department = (SELECT department FROM students WHERE enrollment_no = %s)
          AND sub.semester = (SELECT semester FROM students WHERE enrollment_no = %s)
        GROUP BY sub.subject_id, sub.subject_name
    """, (enrollment_no, enrollment_no, enrollment_no))
    attn_subjects = cursor.fetchall()
    
    attn_labels = [r['subject_name'] for r in attn_subjects]
    attn_values = [round(float(r['attendance_pct']), 1) for r in attn_subjects]

    # 📈 ANALYTICAL SYNC: GET ADMIN-STYLE CHART DATA (LOCKED TO STUDENT)
    chart_data = analysis.get_dashboard_chart_data({'enrollment_no': enrollment_no})

    conn.close()
    
    return render_template('student/student_dashboard.html', 
                           student=student_info, 
                           marks_list=marks_data, 
                           summary=perf_summary,
                           fb_stats=fb_stats,
                           subjects=[m['subject'] for m in marks_data],
                           marks=[m['total'] for m in marks_data],
                           attn_labels=attn_labels,
                           attn_values=attn_values,
                           chart_data=chart_data)

@student_bp.route('/api/stats')
def student_api_stats():
    """Secure API endpoint for student dashboard analytics"""
    enrollment_no = session.get('student_id')
    if not enrollment_no:
        return {"error": "Unauthorized"}, 401
    
    # Force enrollment_no filter to ensure data privacy
    filters = {'enrollment_no': enrollment_no}
    chart_data = analysis.get_dashboard_chart_data(filters)
    
    return {"chart_data": chart_data}

# 📈 ACADEMIC TRACKING: PERFORMANCE
@student_bp.route('/performance')
def performance():
    enrollment_no = session['student_id']
    student_info = analysis.get_student_details(enrollment_no)
    marks_data = analysis.get_student_marks(enrollment_no)
    perf_summary = analysis.calculate_student_summary(enrollment_no)

    # 🛰️ SUBJECT-WISE ATTENDANCE ANALYSIS
    conn = analysis.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT sub.subject_name,
               COALESCE((SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(a.attendance_id), 0)), 0) as attendance_pct
        FROM subjects sub
        LEFT JOIN attendance a ON sub.subject_id = a.subject_id AND a.enrollment_no = %s
        WHERE sub.department = (SELECT department FROM students WHERE enrollment_no = %s)
          AND sub.semester = (SELECT semester FROM students WHERE enrollment_no = %s)
        GROUP BY sub.subject_id, sub.subject_name
    """, (enrollment_no, enrollment_no, enrollment_no))
    attn_subjects = cursor.fetchall()
    
    attn_labels = [r['subject_name'] for r in attn_subjects]
    attn_values = [round(float(r['attendance_pct']), 1) for r in attn_subjects]
    conn.close()
    
    # Advanced logic for highlights
    highest_sub = max(marks_data, key=lambda x: x['total']) if marks_data else None
    lowest_sub = min(marks_data, key=lambda x: x['total']) if marks_data else None
    total_marks_sum = sum(m['total'] for m in marks_data)
    
    # 📈 ANALYTICAL SYNC: GET ADMIN-STYLE CHART DATA (LOCKED TO STUDENT)
    chart_data = analysis.get_dashboard_chart_data({'enrollment_no': enrollment_no})

    return render_template('student/performance.html', 
                           student=student_info, 
                           marks_list=marks_data, 
                           summary=perf_summary,
                           highlights={'highest': highest_sub, 'lowest': lowest_sub, 'total_sum': total_marks_sum},
                           subjects=[m['subject'] for m in marks_data],
                           marks=[m['total'] for m in marks_data],
                           attn_labels=attn_labels,
                           attn_values=attn_values,
                           chart_data=chart_data)

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
            flash("Identity credentials secured. Protocol complete.", "success")
            return redirect(url_for('student.dashboard'))
        else:
            conn.close()
            flash("Identity verification failed. Current credentials incorrect.", "danger")
            
    return render_template('student/change_password.html')

# 👤 IDENTITY SECTOR: PROFILE MANAGEMENT
@student_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    enrollment_no = session['student_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        cursor.execute("UPDATE students SET email=%s, phone=%s WHERE enrollment_no=%s", 
                       (email, phone, enrollment_no))
        conn.commit()
        flash("Identity record synchronized successfully.", "success")
        return redirect(url_for('student.profile'))
        
    cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
    student_info = cursor.fetchone()
    conn.close()
    return render_template('student/profile.html', student=student_info)

# 💬 COMMUNICATION: FEEDBACK
@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback():
    enrollment_no = session['student_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        subject = request.form.get('subject')
        feedback_type = request.form.get('feedback_type')
        message = request.form.get('message')
        
        if message and feedback_type:
            # Fetch student details for record redundancy
            cursor.execute("SELECT name, department, semester FROM students WHERE enrollment_no = %s", (enrollment_no,))
            student = cursor.fetchone()
            
            if student:
                cursor.execute("""
                    INSERT INTO feedback (student_id, student_name, department, semester, subject, feedback_type, comment, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
                """, (enrollment_no, student['name'], student['department'], student['semester'], subject, feedback_type, message))
                conn.commit()
                flash("Institutional feedback submitted successfully.", "success")
                return redirect(url_for('student.feedback'))
    
    # Fetch history for the logged-in student ONLY
    cursor.execute("SELECT * FROM feedback WHERE student_id = %s ORDER BY date DESC", (enrollment_no,))
    history = cursor.fetchall()
    
    # Fetch student's subjects for the dropdown
    cursor.execute("SELECT subject_name FROM subjects WHERE department = (SELECT department FROM students WHERE enrollment_no = %s) AND semester = (SELECT semester FROM students WHERE enrollment_no = %s)", (enrollment_no, enrollment_no))
    subjects = [r['subject_name'] for r in cursor.fetchall()]
    
    student_info = analysis.get_student_details(enrollment_no)
    conn.close()
    return render_template('student/feedback.html', student=student_info, history=history, subjects=subjects)

# 🚪 SESSION TERMINATION: LOGOUT
@student_bp.route('/logout')
def logout():
    session.clear()
    flash("Session terminated successfully.", "info")
    return redirect(url_for('student.login'))
