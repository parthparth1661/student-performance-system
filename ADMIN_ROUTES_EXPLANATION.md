# Admin Routes Complete Documentation

**File**: `admin_routes.py`  
**Type**: Flask Blueprint for administrative operations  
**Lines**: ~1,838  
**Purpose**: Manage all backend operations for student performance system

---

## Table of Contents
1. [Imports & Setup](#imports--setup)
2. [Authentication](#authentication)
3. [Dashboard](#dashboard)
4. [Students Module](#students-module)
5. [Subjects Module](#subjects-module)
6. [Faculty Module](#faculty-module)
7. [Marks Module](#marks-module)
8. [Attendance Module](#attendance-module)
9. [CSV Uploads](#csv-uploads)
10. [Data Management](#data-management)
11. [Reports & Export](#reports--export)
12. [Admin Profile](#admin-profile)
13. [Feedback Module](#feedback-module)
14. [AJAX Endpoints](#ajax-endpoints)

---

## IMPORTS & SETUP

### Purpose
Initialize Flask application, import dependencies, and create blueprint.

### Code

```python
from datetime import date, datetime
import os
import math
import csv
from io import StringIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from analysis import get_dashboard_stats, get_performance_overview, get_dashboard_chart_data

admin_bp = Blueprint('admin', __name__)
```

### Explanation

| Import | Purpose |
|--------|---------|
| `datetime` | Work with dates/times for attendance, reports |
| `os` | File system operations (uploads, directories) |
| `math` | Pagination calculations (`math.ceil()`) |
| `csv, StringIO` | Parse CSV files for bulk uploads |
| `Blueprint` | Create modular routing system |
| `render_template` | Render HTML with data |
| `request` | Access form data, files, query params |
| `redirect, url_for` | Navigate between routes |
| `flash` | User notifications |
| `session` | Store login data |
| `jsonify` | Return JSON for AJAX |
| `check/generate_password_hash` | Secure password handling |
| `get_db_connection` | Database connection from db.py |

---

## AUTHENTICATION

### Purpose
Protect admin routes and manage login/logout.

### Before Request Hook

```python
@admin_bp.before_request
def check_admin_login():
    """Runs before EVERY admin route"""
    if request.endpoint in ['admin.login', 'admin.logout', 'admin.static']: 
        return  # These routes don't require authentication
    if not session.get('admin_id'):
        return redirect(url_for('admin.login'))
```

**What it does**:
- Executes before every request to admin routes
- Allows login, logout, and static files without auth
- Redirects unauthenticated users to login page
- Acts as security middleware

### Login Route

```python
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 🕵️ DEBUG: MONITOR SESSION STATE
    print("Session:", session)
    
    # ❌ IF ADMIN_ID EXISTS IN GET REQUEST -> CLEAR IT (FORCE LOGIN)
    if request.method == 'GET' and 'admin_id' in session:
        session.clear()
        print("Stale session cleared. Forcing re-authentication.")

    if request.method == 'POST':
        # Get credentials from form
        email = request.form.get('email') or request.form.get('username')
        password = request.form.get('password')
        
        # Get database connection
        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('admin/admin_login.html')
        
        cursor = conn.cursor(dictionary=True)
        try:
            # Query admin by email
            cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
            admin = cursor.fetchone()
            
            # Verify password (hashed)
            if admin and check_password_hash(admin['password'], password):
                # ✅ LOGIN SUCCESSFUL: Set session variables
                session['admin_id'] = admin['admin_id']
                session['admin_email'] = admin['email']
                session['admin_logged_in'] = True
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
```

**Key Features**:
- **GET request while logged in**: Clears session (force re-login)
- **POST request**: Validates credentials against database
- **Password verification**: Uses `check_password_hash()` for security
- **Session creation**: Stores admin_id, email, logged_in flag
- **Error handling**: Database errors, invalid credentials

### Logout Route

```python
@admin_bp.route('/logout')
def logout():
    session.clear()  # Remove all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('admin.login'))
```

---

## DASHBOARD

### Purpose
Display analytics, top performers, and risk alerts with filters.

### Main Dashboard Route

```python
@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    print("Session:", session)
    
    # 🛡️ STRICT SESSION PROTECTION
    if 'admin_id' not in session:
        return redirect(url_for('admin.login'))

    # 🎯 STEP 1: GET FILTER VALUES
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

    # 📊 STEP 2: GENERATE ANALYTICS
    stats = get_dashboard_stats(filters)
    chart_data = get_dashboard_chart_data(filters)
    
    # 📋 STEP 3: FETCH ANALYTICS WITH FILTERS
    from analysis import build_dashboard_conditions
    where_clause, values = build_dashboard_conditions(filters)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. TOP PERFORMERS (Top 5 students by average marks)
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

    # 2. RISK ALERTS - CRITICAL MARKS (< 40)
    cursor.execute(f"""
        SELECT DISTINCT s.name, 'Critical Score' as reason
        FROM students s
        JOIN marks m ON s.enrollment_no = m.enrollment_no
        JOIN subjects sub ON m.subject_id = sub.subject_id
        {where_clause} AND m.total_marks < 40
    """, values)
    low_marks = cursor.fetchall()

    # 3. RISK ALERTS - LOW ATTENDANCE (< 75%)
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
    
    # MERGE & DEDUPLICATE ALERTS
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
```

**Features**:
- **Dynamic filtering**: Department, Semester, Search, Subject
- **Real-time analytics**: Top performers, risk alerts
- **Alert merging**: Combines multiple alert types per student
- **Subjects dropdown**: For filter options

### API Endpoint for Dynamic Updates

```python
@admin_bp.route('/dashboard/api/stats')
def dashboard_api_stats():
    """API Endpoint for dashboard updates WITHOUT page reloads"""
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'subject': request.args.get('subject')
    }
    
    # Get stats and charts
    stats = get_dashboard_stats(filters)
    chart_data = get_dashboard_chart_data(filters)
    
    # Get filtered leaderboard & risks (same queries as dashboard)
    from analysis import build_dashboard_conditions
    where_clause, values = build_dashboard_conditions(filters)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # [Same queries as dashboard...]
    
    cursor.close()
    conn.close()

    # RETURN JSON FOR JAVASCRIPT
    return jsonify({
        'stats': stats,
        'chart_data': chart_data,
        'top_students': top_students,
        'low_students': low_students
    })
```

**Purpose**: Frontend JavaScript calls this endpoint → receives JSON → updates dashboard without page reload

---

## STUDENTS MODULE

### Purpose
Manage student records (CRUD operations).

### View Students Route

```python
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

    # BUILD DYNAMIC QUERY
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

    # COUNT TOTAL RECORDS FOR PAGINATION
    count_query = "SELECT COUNT(*) as total FROM (" + query + ") as t"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['total']
    total_pages = math.ceil(total_records / limit)

    # GET PAGINATED DATA
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
```

**Features**:
- **Dynamic filtering**: Department, Semester, Name/Enrollment search
- **Pagination**: 10 records per page with total count
- **LIKE operator**: Partial matching for search

### Add Student Route

```python
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

        # 🇮🇳 INDIAN MOBILE VALIDATION (10 digits, starts with 6-9)
        if contact_no and not re.match(r'^[6-9]\d{9}$', contact_no):
            flash("Invalid Identity: Please enter a valid 10-digit Indian mobile number.", "warning")
            return render_template('admin/add_student.html', form_data=request.form)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # CHECK UNIQUENESS
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no = %s", (enrollment_no,))
            if cursor.fetchone():
                flash("ID Conflict: Enrollment number already exists.", "danger")
                return render_template('admin/add_student.html', form_data=request.form)

            # DEFAULT PASSWORD = ENROLLMENT_NO (HASHED)
            pw_hash = generate_password_hash(enrollment_no)
            
            # INSERT NEW STUDENT
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
```

**Features**:
- **Mobile validation**: Regex `^[6-9]\d{9}$` ensures Indian format
- **Unique enrollment**: Prevents duplicate enrollment numbers
- **Default password**: Enrollment number hashed for security
- **Parameterized queries**: Protection against SQL injection

### Edit Student Route

```python
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

        # VALIDATE MOBILE
        if contact_no and not re.match(r'^[6-9]\d{9}$', contact_no):
            flash("Invalid Identity: Please enter a valid 10-digit Indian mobile number.", "warning")
            student_data = dict(request.form)
            student_data['enrollment_no'] = enrollment_no
            return render_template('admin/add_student.html', student=student_data, edit_mode=True)
        
        try:
            # UPDATE EXISTING STUDENT
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
    
    # FETCH STUDENT FOR PRE-FILL FORM
    cursor.execute("SELECT * FROM students WHERE enrollment_no = %s", (enrollment_no,))
    student = cursor.fetchone()
    conn.close()
    
    if not student:
        flash("Record Missing: Identity not found.", "danger")
        return redirect(url_for('admin.view_students'))
        
    return render_template('admin/add_student.html', student=student, edit_mode=True)
```

### Delete Student Route

```python
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
```

---

## SUBJECTS MODULE

### Purpose
Manage courses and faculty assignments.

### View Subjects with Faculty

```python
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
    
    # JOIN WITH FACULTY TABLE
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

    # COUNT FOR PAGINATION
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
```

**Features**:
- **LEFT JOIN**: Includes subjects even without faculty
- **COUNT replacement**: Clever pagination counting
- **Faculty name display**: Shows assigned faculty

### Add Subject

```python
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
```

---

## FACULTY MODULE

### Purpose
Manage faculty members and their subject assignments.

### View Faculty with Mapped Subjects

```python
@admin_bp.route('/faculty')
def view_faculty():
    department = request.args.get('department')
    search = request.args.get('search')
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # GROUP_CONCAT: Combine subjects into comma-separated string
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

    # COUNT FOR PAGINATION
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit) if total_records > 0 else 1

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
```

**Features**:
- **GROUP_CONCAT**: Combines multiple subjects into single row
- **Example output**: "Math, Physics, Chemistry"
- **Subquery pagination**: Complex counting technique

---

## MARKS MODULE

### Purpose
Track student marks (Internal + Viva + External = Total).

### View Marks with Statistics

```python
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
    
    # BUILD QUERY WITH JOINS
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

    # 📊 CALCULATE SUMMARY STATISTICS
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

    # PAGINATION
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    query += " ORDER BY m.id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    marks_list = cursor.fetchall()

    # 📊 SUBJECT-WISE AVERAGES FOR CHART
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

    # FETCH SUBJECTS FOR DROPDOWN
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
```

**Features**:
- **Multi-filter support**: Enrollment, Department, Semester, Subject, Exam Type
- **Statistics calculation**: Average, Top Score, Pass Count
- **Chart data**: Subject-wise averages for visualization

### Add/Update Marks (Upsert)

```python
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
            # 🛡️ UPSERT LOGIC: Update if exists, Insert if new
            cursor.execute("SELECT id FROM marks WHERE enrollment_no = %s AND subject_id = %s", (enrollment_no, subject_id))
            existing = cursor.fetchone()
            
            if existing:
                # UPDATE EXISTING RECORD
                cursor.execute("""
                    UPDATE marks 
                    SET internal_marks = %s, viva_marks = %s, external_marks = %s, total_marks = %s 
                    WHERE id = %s
                """, (i_marks, v_marks, e_marks, total, existing['id']))
            else:
                # INSERT NEW RECORD
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
```

**Features**:
- **Upsert pattern**: Checks if record exists before insert/update
- **Automatic total**: Calculates total from internal + viva + external
- **Duplicate prevention**: Same student-subject combo updates existing record

---

## ATTENDANCE MODULE

### Purpose
Track student attendance and generate reports.

### View Attendance with Low Attendance Alerts

```python
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
    
    # BUILD QUERY WITH JOINS
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

    # 📊 CALCULATE SUMMARY STATISTICS
    stats_query = f"""
        SELECT 
            COUNT(*) as total_classes,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM ({query}) as filtered_att
    """
    cursor.execute(stats_query, params)
    att_stats = cursor.fetchone()
    
    # CALCULATE ATTENDANCE PERCENTAGE
    if att_stats and att_stats['total_classes'] > 0:
        att_stats['percent'] = round((att_stats['present_count'] / att_stats['total_classes']) * 100, 2)
    else:
        att_stats = {'total_classes': 0, 'present_count': 0, 'absent_count': 0, 'percent': 0}

    # ⚠️ ALERT SYSTEM: FIND LOW ATTENDANCE STUDENTS (<75%)
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

    # PAGINATION
    count_query = f"SELECT COUNT(*) as count FROM ({query}) as sub_query"
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['count']
    total_pages = math.ceil(total_records / limit)

    # FETCH PAGINATED DATA
    query += " ORDER BY a.date DESC, a.attendance_id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    cursor.execute(query, params)
    attendance_list = cursor.fetchall()

    # SUBJECTS FOR DROPDOWN
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
```

**Features**:
- **Percentage calculation**: (Present ÷ Total) × 100
- **Low attendance alerts**: Students with <75% marked
- **NULLIF protection**: Prevents division by zero
- **Comprehensive filtering**: Date, Status, Subject, Department, Semester

### Add Single Attendance

```python
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
        
        # ⚠️ VALIDATION
        if not all([enrollment_no, subject_id, att_date, status]):
            flash("All fields are required!", "danger")
        else:
            # 🛡️ PREVENT DUPLICATE ENTRY
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
```

### Bulk Attendance (Entire Class)

```python
@admin_bp.route('/attendance/bulk', methods=['GET', 'POST'])
def bulk_attendance():
    department = request.args.get('department', 'BCA')
    semester = request.args.get('semester', '1')
    subject_id = request.args.get('subject_id')
    att_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # FETCH SUBJECTS & STUDENTS FOR CONTEXT
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()
    
    if not subject_id and subjects:
        subject_id = subjects[0]['subject_id']

    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s", (department, semester))
    students = cursor.fetchall()

    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        att_date = request.form.get('date')
        
        if not subject_id or not att_date:
            flash("Integration Error: Subject and Date credentials are required.", "danger")
        else:
            success_count = 0
            for student in students:
                status = request.form.get(f"status_{student['enrollment_no']}")
                if status:
                    # CHECK FOR EXISTING RECORD
                    cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no = %s AND subject_id = %s AND date = %s", 
                                 (student['enrollment_no'], subject_id, att_date))
                    if not cursor.fetchone():
                        # INSERT NEW RECORD
                        cursor.execute("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)",
                                     (student['enrollment_no'], subject_id, att_date, status))
                        success_count += 1
            
            conn.commit()
            if success_count > 0:
                flash(f"Success: {success_count} attendance records synchronized!", "success")
            else:
                flash("Information: No new records were added (may already exist).", "info")
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
```

**Features**:
- **Form naming convention**: `status_{enrollment_no}` for each student
- **Bulk insert**: Multiple records in single POST
- **Duplicate prevention**: Checks before inserting each record

### Attendance Report (Monthly)

```python
@admin_bp.route('/attendance/report')
def attendance_report():
    department = request.args.get('department', 'BCA')
    semester = request.args.get('semester', '1')
    subject_id = request.args.get('subject_id')
    month_val = request.args.get('month', datetime.now().month, type=int)
    year_val = request.args.get('year', datetime.now().year, type=int)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # FETCH SUBJECTS FOR CONTEXT
    cursor.execute("SELECT subject_id, subject_name FROM subjects WHERE department = %s AND semester = %s", (department, semester))
    subjects = cursor.fetchall()
    
    if not subject_id and subjects:
        subject_id = subjects[0]['subject_id']

    # FETCH AGGREGATED REPORT DATA
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
```

**Features**:
- **Date filtering**: MONTH() and YEAR() functions
- **LEFT JOIN**: Includes students even with no attendance
- **Average calculation**: Per-student and class-wide percentages

---

## CSV UPLOADS

### Purpose
Bulk import data from CSV files.

### Upload Faculty CSV

```python
@admin_bp.route('/upload_faculty_csv', methods=['POST'])
def upload_faculty_csv():
    if 'file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('admin.view_faculty'))
    
    file = request.files['file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('admin.view_faculty'))

    if file and file.filename.endswith('.csv'):
        try:
            # READ AND DECODE FILE
            content = file.stream.read().decode("utf-8")
            stream = StringIO(content)
            csv_reader = csv.DictReader(stream)
            
            # NORMALIZE HEADERS (lowercase, strip whitespace)
            csv_reader.fieldnames = [f.strip().lower() for f in csv_reader.fieldnames]
            
            # DETERMINE NAME COLUMN (fallback to faculty_name if name missing)
            if 'faculty_name' in csv_reader.fieldnames and 'name' not in csv_reader.fieldnames:
                name_col = 'faculty_name'
            else:
                name_col = 'name'

            conn = get_db_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_count = 0
            
            # ITERATE THROUGH CSV ROWS
            for row in csv_reader:
                name = row.get(name_col, '').strip()
                email = row.get('email', '').strip()
                contact = row.get('contact_no', '').strip()
                dept = row.get('department', '').strip()
                
                # 🛡️ VALIDATION
                if not all([name, email, dept]):
                    error_count += 1
                    continue
                
                # EMAIL VALIDATION
                if '@' not in email or '.' not in email:
                    error_count += 1
                    continue
                    
                # CONTACT VALIDATION (10 digits)
                if len(contact) != 10 or not contact.isdigit():
                    error_count += 1
                    continue

                try:
                    # INSERT OR UPDATE IF EXISTS
                    cursor.execute("""
                        INSERT INTO faculty (faculty_name, email, contact_no, department)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            faculty_name=VALUES(faculty_name),
                            department=VALUES(department),
                            contact_no=VALUES(contact_no)
                    """, (name, email, contact, dept))
                    success_count += 1
                except Exception as db_err:
                    print(f"DB Insert Error: {db_err}")
                    error_count += 1
            
            conn.commit()
            conn.close()
            
            if success_count > 0:
                flash(f"CSV uploaded successfully. {success_count} records synchronized.", "success")
            if error_count > 0:
                flash(f"{error_count} records skipped due to validation errors.", "warning")
                
        except Exception as e:
            flash(f"System Error: {str(e)}", "danger")
    else:
        return redirect(url_for('admin.view_faculty'))
    
    return redirect(url_for('admin.view_faculty'))
```

**Features**:
- **CSV parsing**: DictReader with header normalization
- **Flexible headers**: Handles both 'name' and 'faculty_name'
- **Validation**: Email format, 10-digit contact
- **ON DUPLICATE KEY UPDATE**: Upsert pattern for CSV
- **Error tracking**: Success/failure counts

### Upload Subject CSV

```python
@admin_bp.route('/upload_subject_csv', methods=['POST'])
def upload_subject_csv():
    if 'file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('admin.view_subjects'))
    
    file = request.files['file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('admin.view_subjects'))

    if file and file.filename.endswith('.csv'):
        try:
            content = file.stream.read().decode("utf-8")
            stream = StringIO(content)
            csv_reader = csv.DictReader(stream)
            
            # NORMALIZE HEADERS
            csv_reader.fieldnames = [f.strip().lower() for f in csv_reader.fieldnames]
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 🧪 FETCH ALL FACULTY FOR QUICK MAPPING
            cursor.execute("SELECT faculty_id, faculty_name FROM faculty")
            faculty_map = {row['faculty_name'].strip().lower(): row['faculty_id'] for row in cursor.fetchall()}
            
            success_count = 0
            error_count = 0
            
            # ITERATE THROUGH CSV ROWS
            for row in csv_reader:
                s_name = (row.get('subject_name') or row.get('name', '')).strip()
                dept = row.get('department', '').strip()
                sem = row.get('semester', '').strip()
                f_name = row.get('faculty_name', '').strip()
                
                if not all([s_name, dept, sem]):
                    error_count += 1
                    continue
                
                # RESOLVE FACULTY_ID FROM MAP
                f_id = faculty_map.get(f_name.lower()) if f_name else None
                
                try:
                    # CHECK IF SUBJECT EXISTS
                    cursor.execute("""
                        SELECT subject_id FROM subjects 
                        WHERE subject_name = %s AND department = %s AND semester = %s
                    """, (s_name, dept, sem))
                    
                    if cursor.fetchone():
                        # UPDATE FACULTY IF SUBJECT EXISTS
                        cursor.execute("""
                            UPDATE subjects SET faculty_id = %s 
                            WHERE subject_name = %s AND department = %s AND semester = %s
                        """, (f_id, s_name, dept, sem))
                    else:
                        # INSERT NEW SUBJECT
                        cursor.execute("""
                            INSERT INTO subjects (subject_name, department, semester, faculty_id)
                            VALUES (%s, %s, %s, %s)
                        """, (s_name, dept, sem, f_id))
                    success_count += 1
                except Exception as db_err:
                    print(f"DB Error: {db_err}")
                    error_count += 1
            
            conn.commit()
            conn.close()
            
            if success_count > 0:
                flash(f"Course Catalogue Updated: {success_count} subjects synchronized.", "success")
            if error_count > 0:
                flash(f"{error_count} entries skipped due to format inconsistencies.", "warning")
                
        except Exception as e:
            flash(f"System Error: {str(e)}", "danger")
    else:
        flash("Invalid protocol. Please upload a .csv file.", "danger")
        
    return redirect(url_for('admin.view_subjects'))
```

**Features**:
- **Faculty mapping**: Builds dictionary for O(1) lookups
- **Duplicate handling**: Updates if exists, inserts if new
- **Flexible naming**: Handles both 'subject_name' and 'name'

---

## DATA MANAGEMENT

### Purpose
Clear system data for testing/reset.

### Reset All Data

```python
@admin_bp.route('/reset-data')
def reset_data():
    # Only reset dynamic data (not admin)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # DISABLE FOREIGN KEY CHECKS TEMPORARILY
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        # TRUNCATE TABLES (faster than DELETE)
        tables = ['attendance', 'marks', 'subjects', 'students', 'faculty']
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        
        # RE-ENABLE FOREIGN KEY CHECKS
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        flash("All system data has been safely reset.", "success")
    except Exception as e:
        flash(f"Error resetting data: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.dashboard'))
```

**Purpose**:
- **TRUNCATE**: Delete all rows (faster than DELETE)
- **Disable FK**: Allows truncate even with foreign key constraints
- **Re-enable FK**: Restores data integrity protection

### Clear Individual Tables

```python
@admin_bp.route('/clear-attendance')
def clear_attendance():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE attendance")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        conn.close()
        flash("All attendance records deleted successfully", "success")
    except Exception as e:
        flash(f"System Error: {e}", "danger")
    return redirect(url_for('admin.view_attendance'))

# Similar for: clear_students, clear_marks, clear_subjects, clear_faculty
```

---

## REPORTS & EXPORT

### Purpose
Generate and export student performance reports.

### Student Report View

```python
@admin_bp.route('/student-report/<enrollment_no>')
def student_report_view(enrollment_no):
    from analysis import get_student_details, get_student_marks, calculate_student_summary
    
    # GET STUDENT BASIC INFO
    student = get_student_details(enrollment_no)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('admin.view_students'))
    
    marks_list = get_student_marks(enrollment_no)
    summary = calculate_student_summary(enrollment_no)
    
    # FETCH ATTENDANCE DATA
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. ATTENDANCE SUMMARY
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
    
    # 2. DETAILED ATTENDANCE (Recent 10)
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
```

**Features**:
- **Comprehensive report**: Marks + Attendance + Summary
- **Recent attendance**: Last 10 records
- **Attendance percentage**: With division-by-zero protection

### Download Student Report PDF

```python
@admin_bp.route('/student-report/<enrollment_no>/download')
def download_student_report(enrollment_no):
    from analysis import generate_student_report_pdf
    from flask import send_file
    
    file_path = generate_student_report_pdf(enrollment_no)
    if file_path and os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    
    flash("Error generating PDF report.", "danger")
    return redirect(url_for('admin.student_report_view', enrollment_no=enrollment_no))
```

### View Reports (Consolidated)

```python
@admin_bp.route('/reports')
def view_reports():
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject')
    }
    
    from analysis import get_report_data
    data = get_report_data(filters)
    
    # GET SUBJECTS FOR FILTER DROPDOWN
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
```

### Export Reports

```python
@admin_bp.route('/reports/export/csv')
def export_csv():
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject')
    }
    from analysis import export_report_csv
    from flask import send_file
    
    file_path = export_report_csv(filters)
    if file_path:
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
    from flask import send_file
    
    data = get_report_data(filters)
    file_path = export_report_pdf(filters, data)
    if file_path:
        return send_file(file_path, as_attachment=True)
    flash("Export failed.", "danger")
    return redirect(url_for('admin.view_reports'))
```

---

## ADMIN PROFILE

### Purpose
Manage admin profile and password.

```python
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
        session['admin_email'] = email  # Update session
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
    
    # VALIDATE NEW PASSWORD
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
    
    # VERIFY CURRENT PASSWORD
    if admin and check_password_hash(admin['password'], current_pw):
        hashed = generate_password_hash(new_pw)
        cursor.execute("UPDATE admin SET password=%s WHERE email=%s", (hashed, admin['email']))
        conn.commit()
        flash("Security credentials updated successfully!", "success")
    else:
        flash("Identity verification failed. Current password incorrect.", "danger")
    
    conn.close()
    return redirect(url_for('admin.profile'))
```

---

## FEEDBACK MODULE

### Purpose
Manage student feedback and admin responses.

```python
@admin_bp.route('/feedback')
def view_feedback():
    f_type = request.args.get('feedback_type', 'All')
    status = request.args.get('status', 'All')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM feedback WHERE 1=1"
    params = []

    if f_type != 'All':
        query += " AND feedback_type = %s"
        params.append(f_type)
        
    if status != 'All':
        query += " AND status = %s"
        params.append(status)

    query += " ORDER BY date DESC"
    cursor.execute(query, params)
    feedback_list = cursor.fetchall()
    
    # SUMMARY STATS
    cursor.execute("SELECT COUNT(*) as total FROM feedback")
    total_feedback = cursor.fetchone()['total'] or 0
    cursor.execute("SELECT COUNT(*) as pending FROM feedback WHERE status = 'Pending'")
    pending_count = cursor.fetchone()['pending'] or 0

    conn.close()
    return render_template('admin/view_feedback.html', 
                         feedback=feedback_list, 
                         total=total_feedback,
                         pending=pending_count,
                         filters={'feedback_type': f_type, 'status': status})

@admin_bp.route('/feedback/reply/<int:feedback_id>', methods=['POST'])
def reply_feedback(feedback_id):
    reply = request.form.get('admin_reply')
    
    if not reply:
        flash("Response content cannot be empty.", "warning")
        return redirect(url_for('admin.view_feedback'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # UPDATE FEEDBACK WITH ADMIN REPLY
        cursor.execute("""
            UPDATE feedback 
            SET admin_reply = %s, status = 'Replied'
            WHERE feedback_id = %s
        """, (reply, feedback_id))
        conn.commit()
        flash("Feedback response successfully recorded.", "success")
    except Exception as e:
        flash(f"System Error: {e}", "danger")
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
        flash("Feedback record deleted successfully.", "success")
    except Exception as e:
        flash(f"Deletion Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('admin.view_feedback'))
```

---

## AJAX ENDPOINTS

### Purpose
Return JSON data for dynamic frontend updates.

```python
@admin_bp.route('/get-students')
def get_students():
    dept = request.args.get('department')
    sem = request.args.get('semester')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT enrollment_no, name FROM students WHERE department = %s AND semester = %s ORDER BY name", (dept, sem))
    students = cursor.fetchall()
    conn.close()
    
    # RETURN JSON FOR JAVASCRIPT
    return jsonify({'students': students})

@admin_bp.route('/get-subjects')
def get_subjects():
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
    
    # RETURN JSON FOR JAVASCRIPT
    return jsonify({'subjects': subjects})
```

**Usage**:
- Frontend JavaScript calls: `/admin/get-students?department=BCA&semester=1`
- Receives JSON: `{"students": [...]}`
- Updates dropdown without page reload (AJAX)

---

## KEY PATTERNS

| Pattern | Purpose | Example |
|---------|---------|---------|
| **Dynamic SQL** | Build queries conditionally | `if dept: query += " AND department = %s"` |
| **Pagination** | Handle large datasets | `LIMIT 10 OFFSET (page-1)*10` |
| **Upsert** | INSERT or UPDATE | `ON DUPLICATE KEY UPDATE` |
| **GROUP_CONCAT** | Combine multiple rows | Faculty with all subjects as string |
| **CASE WHEN** | Conditional aggregation | `SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END)` |
| **NULLIF** | Prevent division by zero | `value / NULLIF(denominator, 0)` |
| **Subqueries** | Complex filtering | `FROM (SELECT ...) as filter` |
| **Parameterized Queries** | SQL injection prevention | `%s` placeholders |
| **Transaction commits** | Atomic operations | `conn.commit()` / `conn.rollback()` |

---

## SECURITY MEASURES

✅ **Parameterized Queries**: `%s` placeholders  
✅ **Password hashing**: `generate_password_hash()`  
✅ **Session management**: Check `admin_id` before access  
✅ **Data validation**: Regex, type checking  
✅ **Foreign key integrity**: Disabled temporarily during bulk ops  
✅ **Error handling**: Try/catch/finally with cleanup  
✅ **SQL injection prevention**: Parameterized statements  
✅ **XSS protection**: Flask templates auto-escape HTML  

---

## Summary

The `admin_routes.py` file is a comprehensive Flask blueprint containing **7 main modules**:

1. **Authentication**: Login/Logout with session management
2. **Dashboard**: Analytics, top performers, risk alerts
3. **Students**: CRUD operations with pagination
4. **Subjects**: Course management with faculty assignment
5. **Faculty**: Teacher management and analytics
6. **Marks**: Score tracking with statistics
7. **Attendance**: Attendance management and reporting

Each module follows standard CRUD patterns with proper validation, error handling, and security measures. The code uses dynamic SQL building, pagination, and complex aggregations for real-world educational data management.
