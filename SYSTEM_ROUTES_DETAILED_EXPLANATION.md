# ===========================================
# STUDENT PERFORMANCE DATA ANALYTICS (SPDA) SYSTEM
# Complete Routes Architecture Documentation
# ===========================================
# This document provides comprehensive documentation of all routes in the SPDA system
# Including detailed explanations, code analysis, and architectural patterns
# ===========================================

# ===========================================
# ROUTING ARCHITECTURE OVERVIEW
# ===========================================

## System Architecture
The SPDA system uses a modular Flask Blueprint architecture with two main route modules:

### 1. Admin Routes (`admin_routes.py`)
- **Blueprint:** `admin_bp = Blueprint('admin', __name__)`
- **URL Prefix:** None (root level admin routes)
- **Purpose:** Administrative operations, data management, analytics dashboard
- **Security:** Session-based authentication with role validation
- **Routes Count:** 25+ routes covering all admin functionality

### 2. Student Routes (`student_routes.py`)
- **Blueprint:** `student_bp = Blueprint('student', __name__, url_prefix='/student')`
- **URL Prefix:** `/student` (all student routes prefixed)
- **Purpose:** Student portal, performance viewing, feedback submission
- **Security:** Session-based authentication with data isolation
- **Routes Count:** 8 routes covering student functionality

## Security Architecture
- **Authentication Middleware:** `@bp.before_request` decorators
- **Session Management:** Flask session with encrypted cookies
- **Data Isolation:** Students can only access their own data
- **Password Security:** Werkzeug hashing with forced rotation
- **Input Validation:** Comprehensive form validation and sanitization

## Database Integration
- **Connection Management:** `get_db_connection()` for all database operations
- **Parameterized Queries:** SQL injection prevention
- **Transaction Safety:** Proper commit/rollback handling
- **Connection Pooling:** Efficient database connection management

---

# ===========================================
# ADMIN ROUTES MODULE (`admin_routes.py`)
# ===========================================

## Module Overview
**File:** `student-performance/admin_routes.py`
**Lines:** 2,400+ lines
**Blueprint:** `admin_bp`
**Authentication:** Required for all routes except login/logout

## Core Dependencies
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
from analysis import get_dashboard_stats, get_performance_overview, get_dashboard_chart_data
import csv, math, os
from io import StringIO
from datetime import date, datetime
```

## 1. AUTHENTICATION ROUTES

### 1.1 Login Route
```python
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Admin authentication endpoint with security features.

    GET: Displays login form, clears stale sessions
    POST: Processes credentials and establishes session

    Security Features:
    - Session clearing to prevent stale logins
    - Password hashing verification
    - Session establishment with admin metadata
    - Database connection error handling
    """
```

**Code Flow:**
1. **GET Request:** Clear any existing stale sessions
2. **POST Request:** Extract email/username and password
3. **Database Query:** Fetch admin record by email
4. **Password Verification:** Use Werkzeug `check_password_hash()`
5. **Session Setup:** Store admin_id, email, login status
6. **Success:** Redirect to dashboard with welcome message
7. **Failure:** Display error and re-render login form

**Database Query:**
```sql
SELECT * FROM admin WHERE email = %s
```

**Session Variables Set:**
- `session['admin_id']` - Admin primary key
- `session['admin_email']` - Admin email for profile updates
- `session['admin_logged_in']` - Boolean login status

### 1.2 Logout Route
```python
@admin_bp.route('/logout')
def logout():
    """Session termination with security cleanup."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('admin.login'))
```

**Security Features:**
- Complete session clearing
- User-friendly logout message
- Automatic redirect to login

## 2. DASHBOARD ROUTES

### 2.1 Main Dashboard
```python
@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    """
    Comprehensive analytics dashboard with real-time data.

    Features:
    - Multi-dimensional filtering (department, semester, subject, search)
    - Performance analytics and KPIs
    - Risk alerts for at-risk students
    - Interactive charts and visualizations
    - Top performers leaderboard
    """
```

**Filter Parameters:**
- `department` - Filter by student department
- `semester` - Filter by academic semester
- `search` - Search by student name/enrollment
- `attendance` - Filter by attendance status
- `subject` - Filter by specific subject

**Data Processing:**
1. **Analytics Generation:** `get_dashboard_stats(filters)`
2. **Chart Data:** `get_dashboard_chart_data(filters)`
3. **Top Performers Query:**
```sql
SELECT s.name, AVG(m.total_marks) as avg_marks
FROM students s
JOIN marks m ON s.enrollment_no = m.enrollment_no
JOIN subjects sub ON m.subject_id = sub.subject_id
WHERE [dynamic_conditions]
GROUP BY s.enrollment_no, s.name
ORDER BY avg_marks DESC
LIMIT 5
```

4. **Risk Alerts - Low Marks:**
```sql
SELECT DISTINCT s.name, 'Critical Score' as reason
FROM students s
JOIN marks m ON s.enrollment_no = m.enrollment_no
WHERE [conditions] AND m.total_marks < 40
```

5. **Risk Alerts - Low Attendance:**
```sql
SELECT s.name, 'Low Attendance' as reason
FROM attendance a
JOIN students s ON a.enrollment_no = s.enrollment_no
WHERE [conditions]
GROUP BY s.enrollment_no, s.name
HAVING (SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)*100.0/COUNT(*)) < 75
```

### 2.2 Dashboard API Stats
```python
@admin_bp.route('/dashboard/api/stats')
def dashboard_api_stats():
    """
    AJAX endpoint for dynamic dashboard updates.

    Returns: JSON with stats, chart_data, top_students, low_students
    Purpose: Real-time dashboard updates without page reload
    """
```

**Response Format:**
```json
{
    "stats": {...},
    "chart_data": {...},
    "top_students": [{"name": "...", "avg_marks": 85.5}],
    "low_students": [{"name": "...", "reason": "Critical Marks"}]
}
```

## 3. STUDENT MANAGEMENT ROUTES

### 3.1 View Students
```python
@admin_bp.route('/students')
def view_students():
    """
    Paginated student listing with advanced filtering.

    Features:
    - Department and semester filtering
    - Name/enrollment search
    - Pagination (10 records per page)
    - Total count for navigation
    """
```

**Query Building:**
```python
query = "SELECT * FROM students WHERE 1=1"
# Dynamic WHERE clause construction
if department: query += " AND department = %s"
if semester: query += " AND semester = %s"
if search: query += " AND (name LIKE %s OR enrollment_no LIKE %s)"
```

**Pagination Logic:**
```python
page = request.args.get('page', 1, type=int)
limit = 10
offset = (page - 1) * limit
total_pages = math.ceil(total_records / limit)
```

### 3.2 Add Student
```python
@admin_bp.route('/students/add', methods=['GET', 'POST'])
def add_student():
    """
    Student creation with validation and security.

    Features:
    - Form validation for all required fields
    - Indian mobile number validation (10 digits, 6-9 start)
    - Duplicate enrollment prevention
    - Automatic password generation
    - Secure password hashing
    """
```

**Validation Rules:**
- **Enrollment Number:** Unique constraint check
- **Mobile Number:** Indian format validation `^[6-9]\d{9}$`
- **Required Fields:** enrollment_no, name, email, department, semester
- **Password:** Auto-generated from enrollment number

**Database Operations:**
```sql
-- Uniqueness check
SELECT enrollment_no FROM students WHERE enrollment_no = %s

-- Insert operation
INSERT INTO students (enrollment_no, name, email, department, semester, contact_no, password_hash)
VALUES (%s, %s, %s, %s, %s, %s, %s)
```

### 3.3 Edit Student
```python
@admin_bp.route('/students/edit/<enrollment_no>', methods=['GET', 'POST'])
def edit_student(enrollment_no):
    """
    Student profile editing with data integrity.

    URL Parameter: enrollment_no - Student identifier
    Features: Update all student fields except enrollment_no
    """
```

### 3.4 Delete Student
```python
@admin_bp.route('/students/delete/<enrollment_no>')
def delete_student(enrollment_no):
    """Student removal with cascade handling."""
```

## 4. SUBJECT MANAGEMENT ROUTES

### 4.1 View Subjects
```python
@admin_bp.route('/subjects')
def view_subjects():
    """Subject catalog with department/semester filtering."""
```

### 4.2 Add Subject
```python
@admin_bp.route('/subjects/add', methods=['GET', 'POST'])
def add_subject():
    """Subject creation with faculty assignment."""
```

### 4.3 Edit Subject
```python
@admin_bp.route('/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    """Subject modification with validation."""
```

### 4.4 Delete Subject
```python
@admin_bp.route('/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    """Subject removal with referential integrity."""
```

### 4.5 Upload Subjects CSV
```python
@admin_bp.route('/subjects/upload', methods=['POST'])
def upload_subjects():
    """
    Bulk subject import via CSV upload.

    Features:
    - CSV parsing and validation
    - Faculty name resolution
    - Duplicate handling (update vs insert)
    - Error reporting and success metrics
    """
```

**CSV Format Expected:**
```csv
subject_name,department,semester,faculty_name
"Data Structures","Computer Science","3","Dr. Smith"
```

## 5. FACULTY MANAGEMENT ROUTES

### 5.1 View Faculty
```python
@admin_bp.route('/faculty')
def view_faculty():
    """Faculty listing with department filtering."""
```

### 5.2 Add Faculty
```python
@admin_bp.route('/faculty/add', methods=['GET', 'POST'])
def add_faculty():
    """Faculty creation with department assignment."""
```

### 5.3 Edit Faculty
```python
@admin_bp.route('/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
def edit_faculty(faculty_id):
    """Faculty profile updates."""
```

### 5.4 Delete Faculty
```python
@admin_bp.route('/faculty/delete/<int:faculty_id>')
def delete_faculty(faculty_id):
    """Faculty removal with subject reassignment."""
```

### 5.5 Faculty Analytics
```python
@admin_bp.route('/faculty/analytics')
def faculty_analytics():
    """Faculty performance analytics dashboard."""
```

### 5.6 Faculty Profile
```python
@admin_bp.route('/faculty/profile/<int:faculty_id>')
def faculty_profile(faculty_id):
    """Individual faculty performance details."""
```

## 6. MARKS MANAGEMENT ROUTES

### 6.1 View Marks
```python
@admin_bp.route('/marks')
def view_marks():
    """
    Comprehensive marks management interface.

    Features:
    - Multi-level filtering (department, semester, subject, student)
    - Bulk operations support
    - Performance analytics
    - Export capabilities
    """
```

**Complex Filtering:**
```python
# Dynamic query building with multiple filter combinations
where_clauses = []
params = []

if department: where_clauses.append("s.department = %s")
if semester: where_clauses.append("s.semester = %s")
if subject: where_clauses.append("sub.subject_name = %s")
if search: where_clauses.append("(s.name LIKE %s OR s.enrollment_no LIKE %s)")
```

### 6.2 Add Marks
```python
@admin_bp.route('/add_marks', methods=['GET', 'POST'])
def add_marks():
    """
    Individual marks entry with validation.

    Process:
    1. Student and subject selection
    2. Marks validation (0-100 range)
    3. Duplicate prevention
    4. Database insertion
    """
```

**Validation Logic:**
```python
# Marks range validation
if not (0 <= total_marks <= 100):
    flash("Marks must be between 0 and 100", "danger")

# Duplicate check
cursor.execute("""
    SELECT marks_id FROM marks
    WHERE enrollment_no = %s AND subject_id = %s
""", (enrollment_no, subject_id))
```

### 6.3 Edit Marks
```python
@admin_bp.route('/marks/edit/<int:marks_id>', methods=['GET', 'POST'])
def edit_marks(marks_id):
    """Marks modification with audit trail."""
```

### 6.4 Delete Marks
```python
@admin_bp.route('/marks/delete/<int:marks_id>')
def delete_marks(marks_id):
    """Marks removal with confirmation."""
```

### 6.5 Bulk Upload Marks
```python
@admin_bp.route('/marks/upload', methods=['POST'])
def upload_marks():
    """
    Bulk marks import from CSV.

    Features:
    - Student enrollment resolution
    - Subject name resolution
    - Marks validation
    - Duplicate handling
    - Progress reporting
    """
```

## 7. ATTENDANCE MANAGEMENT ROUTES

### 7.1 View Attendance
```python
@admin_bp.route('/attendance')
def view_attendance():
    """Attendance records with comprehensive filtering."""
```

### 7.2 Mark Attendance
```python
@admin_bp.route('/attendance/mark', methods=['GET', 'POST'])
def mark_attendance():
    """
    Daily attendance marking interface.

    Features:
    - Subject-wise attendance
    - Bulk status updates
    - Date validation
    - Duplicate prevention
    """
```

### 7.3 Bulk Attendance Upload
```python
@admin_bp.route('/attendance/bulk_upload', methods=['POST'])
def bulk_upload_attendance():
    """CSV-based bulk attendance import."""
```

## 8. REPORTING ROUTES

### 8.1 Student Reports
```python
@admin_bp.route('/reports/student/<enrollment_no>')
def student_report(enrollment_no):
    """Individual student performance report."""
```

### 8.2 Attendance Reports
```python
@admin_bp.route('/reports/attendance')
def attendance_report():
    """Attendance analytics and summaries."""
```

### 8.3 Export Reports
```python
@admin_bp.route('/reports/export')
def export_report():
    """Data export in various formats (CSV, PDF)."""
```

## 9. ADMIN PROFILE ROUTES

### 9.1 Admin Profile
```python
@admin_bp.route('/profile')
def profile():
    """Admin profile viewing and editing."""
```

### 9.2 Update Profile
```python
@admin_bp.route('/update_profile', methods=['POST'])
def update_profile():
    """Admin profile information updates."""
```

### 9.3 Change Password
```python
@admin_bp.route('/change_password', methods=['POST'])
def change_password():
    """
    Admin password change with security validation.

    Features:
    - Current password verification
    - New password confirmation
    - Secure hashing
    - Session integrity
    """
```

## 10. FEEDBACK MANAGEMENT ROUTES

### 10.1 View Feedback
```python
@admin_bp.route('/feedback')
def view_feedback():
    """
    Feedback management interface.

    Features:
    - Feedback filtering by type and status
    - Response management
    - Analytics and summaries
    """
```

**Filtering Options:**
- `feedback_type`: Academic, Administrative, Technical, Other
- `status`: All, Pending, Replied

### 10.2 Reply to Feedback
```python
@admin_bp.route('/feedback/reply/<int:feedback_id>', methods=['POST'])
def reply_feedback(feedback_id):
    """
    Admin response to student feedback.

    Process:
    1. Update feedback record with admin reply
    2. Change status to 'Replied'
    3. Maintain audit trail
    """
```

### 10.3 Delete Feedback
```python
@admin_bp.route('/feedback/delete/<int:feedback_id>')
def delete_feedback(feedback_id):
    """Feedback record removal."""
```

## 11. ASYNC API ENDPOINTS

### 11.1 Get Students API
```python
@admin_bp.route('/get-students')
def get_students():
    """
    AJAX endpoint for dynamic student dropdowns.

    Parameters:
    - department: Filter by department
    - semester: Filter by semester

    Returns: JSON array of students
    """
    return jsonify({'students': students})
```

### 11.2 Get Subjects API
```python
@admin_bp.route('/get-subjects')
def get_subjects():
    """
    AJAX endpoint for dynamic subject dropdowns.

    Parameters:
    - department: Filter by department
    - semester: Filter by semester

    Returns: JSON array of subjects
    """
    return jsonify({'subjects': subjects})
```

---

# ===========================================
# STUDENT ROUTES MODULE (`student_routes.py`)
# ===========================================

## Module Overview
**File:** `student-performance/student_routes.py`
**Lines:** 550+ lines
**Blueprint:** `student_bp`
**URL Prefix:** `/student`
**Authentication:** Required for all routes except login

## Core Dependencies
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import analysis
```

## 1. AUTHENTICATION ROUTES

### 1.1 Student Login
```python
@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Student authentication with security features.

    Features:
    - Session validation
    - Password verification
    - Forced password rotation
    - Session establishment
    """
```

**Security Flow:**
1. **Session Check:** Prevent double login
2. **Credential Verification:** Enrollment + password
3. **Password Rotation:** Force change if using default
4. **Session Setup:** Store student metadata

**Database Query:**
```sql
SELECT * FROM students WHERE enrollment_no = %s
```

### 1.2 Student Logout
```python
@student_bp.route('/logout')
def logout():
    """Secure session termination."""
    session.clear()
    flash("Session terminated successfully.", "info")
    return redirect(url_for('student.login'))
```

## 2. DASHBOARD ROUTES

### 2.1 Student Dashboard
```python
@student_bp.route('/dashboard')
def dashboard():
    """
    Student performance dashboard.

    Features:
    - Personal performance metrics
    - Subject-wise attendance
    - Feedback status
    - Performance highlights
    """
```

**Data Aggregation:**
1. **Student Info:** `analysis.get_student_details(enrollment_no)`
2. **Marks Data:** `analysis.get_student_marks(enrollment_no)`
3. **Performance Summary:** `analysis.calculate_student_summary(enrollment_no)`
4. **Attendance Calculation:** Complex SQL with percentage computation
5. **Subject-wise Attendance:** Department/semester filtered queries

**Key Query - Attendance Percentage:**
```sql
SELECT (COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) as attendance
FROM attendance WHERE enrollment_no = %s
```

**Key Query - Subject-wise Attendance:**
```sql
SELECT sub.subject_name,
       COALESCE((SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(a.attendance_id), 0)), 0) as attendance_pct
FROM subjects sub
LEFT JOIN attendance a ON sub.subject_id = a.subject_id AND a.enrollment_no = %s
WHERE sub.department = (SELECT department FROM students WHERE enrollment_no = %s)
  AND sub.semester = (SELECT semester FROM students WHERE enrollment_no = %s)
GROUP BY sub.subject_id, sub.subject_name
```

### 2.2 Student API Stats
```python
@student_bp.route('/api/stats')
def student_api_stats():
    """
    Secure API endpoint for student dashboard charts.

    Security: Enrollment-based data filtering
    Returns: JSON chart data for authenticated student only
    """
    enrollment_no = session.get('student_id')
    if not enrollment_no:
        return {"error": "Unauthorized"}, 401

    filters = {'enrollment_no': enrollment_no}
    chart_data = analysis.get_dashboard_chart_data(filters)
    return {"chart_data": chart_data}
```

## 3. PERFORMANCE ROUTES

### 3.1 Performance View
```python
@student_bp.route('/performance')
def performance():
    """
    Detailed performance analysis page.

    Features:
    - Subject-wise marks breakdown
    - Attendance analysis
    - Performance highlights
    - Chart visualizations
    """
```

**Performance Highlights:**
```python
highest_sub = max(marks_data, key=lambda x: x['total']) if marks_data else None
lowest_sub = min(marks_data, key=lambda x: x['total']) if marks_data else None
total_marks_sum = sum(m['total'] for m in marks_data)
```

## 4. SECURITY ROUTES

### 4.1 Change Password
```python
@student_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """
    Student password change with validation.

    Features:
    - Current password verification
    - New password confirmation
    - Secure hashing
    - is_password_changed flag management
    """
```

**Process:**
1. **Validation:** Confirm new passwords match
2. **Verification:** Check current password
3. **Update:** Hash and store new password
4. **Flag Update:** Set is_password_changed = TRUE

## 5. PROFILE MANAGEMENT

### 5.1 Student Profile
```python
@student_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """
    Student profile viewing and limited editing.

    Editable Fields: email, phone
    Restricted Fields: enrollment_no, name, department, semester
    """
```

**Update Query:**
```sql
UPDATE students SET email=%s, phone=%s WHERE enrollment_no=%s
```

## 6. FEEDBACK SYSTEM

### 6.1 Student Feedback
```python
@student_bp.route('/feedback', methods=['GET', 'POST'])
def feedback():
    """
    Student feedback submission and history.

    Features:
    - Multi-type feedback (Academic, Administrative, Technical)
    - Subject-specific feedback
    - Feedback history with admin replies
    - Student data isolation
    """
```

**Submission Process:**
1. **Validation:** Check required fields
2. **Student Info Fetch:** Get name, department, semester
3. **Insert Record:** Store feedback with metadata
4. **History Display:** Show all student's feedback

**Insert Query:**
```sql
INSERT INTO feedback (student_id, student_name, department, semester, subject, feedback_type, comment, status)
VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
```

**History Query:**
```sql
SELECT * FROM feedback WHERE student_id = %s ORDER BY date DESC
```

---

# ===========================================
# ROUTE SECURITY ANALYSIS
# ===========================================

## Authentication Patterns

### Admin Routes Security
- **Before Request Hook:** `@admin_bp.before_request`
- **Exempt Routes:** login, logout, static files
- **Session Check:** `if not session.get('admin_id')`
- **Redirect:** `url_for('admin.login')`

### Student Routes Security
- **Before Request Hook:** `@student_bp.before_request`
- **Exempt Routes:** login, static files
- **Session Check:** `if 'student_id' not in session`
- **Redirect:** `url_for('student.login')`

## Data Isolation Security

### Student Data Access
```python
# All student queries include enrollment filter
enrollment_no = session['student_id']
# Example: WHERE enrollment_no = %s
```

### Admin Data Access
```python
# Admins can access all data (no filters)
# But operations are logged and audited
```

## Input Validation

### Form Validation
- **Required Fields:** Server-side validation
- **Data Types:** Type conversion and checking
- **Format Validation:** Email, phone number formats
- **Range Validation:** Marks (0-100), percentages

### SQL Injection Prevention
- **Parameterized Queries:** All database operations
- **Input Sanitization:** Flask-WTF or manual cleaning
- **Type Casting:** URL parameters (`type=int`)

## Session Security

### Session Variables
**Admin Session:**
```python
session['admin_id']      # Primary key
session['admin_email']   # For profile updates
session['admin_logged_in'] # Status flag
```

**Student Session:**
```python
session['student_id']        # Enrollment number
session['student_name']      # Display name
session['student_dept']      # Department
session['is_password_changed'] # Security flag
```

### Session Management
- **Clear on Logout:** Complete session clearing
- **Stale Prevention:** Session clearing on login page
- **Timeout Handling:** Flask default session timeout

---

# ===========================================
# DATABASE INTEGRATION PATTERNS
# ===========================================

## Connection Management
```python
# Standard pattern across all routes
conn = get_db_connection()
try:
    cursor = conn.cursor(dictionary=True)
    # Database operations
    conn.commit()
finally:
    cursor.close()
    conn.close()
```

## Query Patterns

### SELECT Operations
```python
cursor.execute("SELECT * FROM table WHERE condition = %s", (param,))
result = cursor.fetchone()  # Single record
results = cursor.fetchall()  # Multiple records
```

### INSERT Operations
```python
cursor.execute("""
    INSERT INTO table (col1, col2) VALUES (%s, %s)
""", (val1, val2))
conn.commit()
```

### UPDATE Operations
```python
cursor.execute("""
    UPDATE table SET col1 = %s WHERE id = %s
""", (new_val, id_val))
conn.commit()
```

### DELETE Operations
```python
cursor.execute("DELETE FROM table WHERE id = %s", (id_val,))
conn.commit()
```

## Complex Queries

### Analytics Queries
- **JOIN Operations:** Multi-table data aggregation
- **Aggregate Functions:** COUNT, AVG, SUM, MAX, MIN
- **Conditional Aggregation:** CASE WHEN statements
- **Subqueries:** Nested SELECT statements

### Dynamic Query Building
```python
# Common pattern for filtering
query = "SELECT * FROM table WHERE 1=1"
params = []

if condition1:
    query += " AND column1 = %s"
    params.append(value1)

if condition2:
    query += " AND column2 LIKE %s"
    params.append(f"%{value2}%")

cursor.execute(query, params)
```

## Error Handling
```python
try:
    # Database operations
    conn.commit()
    flash("Success message", "success")
except Exception as e:
    flash(f"Error: {str(e)}", "danger")
finally:
    conn.close()
```

---

# ===========================================
# API RESPONSE PATTERNS
# ===========================================

## JSON API Endpoints

### Success Response
```python
return jsonify({
    'status': 'success',
    'data': result_data,
    'message': 'Operation completed'
})
```

### Error Response
```python
return jsonify({
    'status': 'error',
    'message': 'Error description'
}), 400
```

### Data Response
```python
return jsonify({
    'students': student_list,
    'subjects': subject_list,
    'total': count
})
```

## HTML Template Responses
```python
return render_template('template.html',
                     data=data,
                     filters=filters,
                     pagination=pagination_info)
```

## File Responses
```python
response = make_response(csv_data)
response.headers['Content-Type'] = 'text/csv'
response.headers['Content-Disposition'] = 'attachment; filename=data.csv'
return response
```

---

# ===========================================
# ROUTE TESTING STRATEGIES
# ===========================================

## Unit Testing Routes
```python
def test_admin_login(client):
    # Test successful login
    response = client.post('/login', data={
        'email': 'admin@example.com',
        'password': 'password'
    })
    assert response.status_code == 302  # Redirect to dashboard

def test_student_dashboard_requires_auth(client):
    # Test authentication requirement
    response = client.get('/student/dashboard')
    assert response.status_code == 302  # Redirect to login
```

## Integration Testing
```python
def test_complete_student_workflow(client):
    # Login
    client.post('/student/login', data={...})

    # Access dashboard
    response = client.get('/student/dashboard')
    assert b'Welcome' in response.data

    # Submit feedback
    client.post('/student/feedback', data={...})

    # Logout
    client.get('/student/logout')
```

## Security Testing
```python
def test_sql_injection_prevention(client):
    # Test parameterized query protection
    response = client.post('/login', data={
        'email': "admin' OR '1'='1",
        'password': 'password'
    })
    assert response.status_code == 200  # Form re-render, not login
```

---

# ===========================================
# PERFORMANCE OPTIMIZATION
# ===========================================

## Database Query Optimization
- **Indexes:** Primary keys, foreign keys, frequently queried columns
- **Pagination:** LIMIT/OFFSET for large datasets
- **Connection Pooling:** Reuse database connections
- **Query Caching:** Cache frequently accessed data

## Route Optimization
- **Static File Caching:** Cache CSS, JS, images
- **Template Caching:** Cache compiled Jinja2 templates
- **Session Optimization:** Minimal session data storage
- **AJAX Loading:** Dynamic content loading

## Code Optimization
- **Import Optimization:** Import only required modules
- **Function Reuse:** Common operations in utility functions
- **Error Handling:** Efficient exception handling
- **Memory Management:** Proper resource cleanup

---

# ===========================================
# MAINTENANCE & DEBUGGING
# ===========================================

## Logging Patterns
```python
# Debug logging in routes
print("Session:", session)
print(f"DEBUG: Processing {operation} for {identifier}")

# Error logging
print(f"CRITICAL: Database Error: {e}")
```

## Route Debugging
```python
# Check current endpoint
print(f"Current endpoint: {request.endpoint}")

# Inspect form data
print(f"Form data: {request.form}")

# Check session state
print(f"Session keys: {list(session.keys())}")
```

## Database Debugging
```python
# Log queries and parameters
print(f"Query: {query}")
print(f"Parameters: {params}")

# Check connection status
print(f"Connection: {conn}")
```

---

# ===========================================
# CONCLUSION
# ===========================================

This comprehensive routes documentation covers:

## Admin Routes (25+ routes)
- Authentication & Security
- Dashboard & Analytics
- CRUD Operations (Students, Subjects, Faculty, Marks, Attendance)
- Bulk Operations & CSV Upload
- Reporting & Export
- Profile Management
- Feedback Management
- AJAX API Endpoints

## Student Routes (8 routes)
- Authentication & Security
- Personal Dashboard
- Performance Analytics
- Profile Management
- Feedback System
- API Endpoints

## Architectural Patterns
- Blueprint Organization
- Security Middleware
- Database Integration
- Error Handling
- Input Validation
- Session Management

## Best Practices
- Code Organization
- Security Implementation
- Performance Optimization
- Testing Strategies
- Maintenance Guidelines

The SPDA system's routing architecture provides a robust, secure, and scalable foundation for educational data management and analytics.</content>
<parameter name="filePath">c:\laragon\www\student-performance-system\SYSTEM_ROUTES_DETAILED_EXPLANATION.md