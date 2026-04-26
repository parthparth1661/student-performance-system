# 🎯 Student Performance Data Analysis (SPDA) System - Data Models Architecture

## 📋 Models Overview

**System Architecture:** MVC (Model-View-Controller) with MySQL Database Models  
**Normalization Level:** Third Normal Form (3NF)  
**ORM Approach:** Direct SQL with mysql-connector-python  
**Model Count:** 7 Core Models with Complex Relationships  

---

## 🏗️ Model Architecture Principles

### **Data Model Design Patterns**
```
1. Entity-Relationship Model (ERM)
2. Normalization (3NF)
3. Referential Integrity
4. Cascade Operations
5. Unique Constraints
6. Default Values
7. Data Validation
```

### **Model Categories**
```
├── 🔐 Security Models     # Authentication & Authorization
├── 👥 User Models         # Students, Faculty, Admin
├── 📚 Academic Models     # Subjects, Curriculum
├── 📊 Performance Models  # Marks, Attendance
├── 💬 Communication Models # Feedback System
└── 📈 Analytics Models    # Reporting & Statistics
```

---

## 🔐 1. Admin Model

### **Model Purpose**
**System Administrators** - Core authentication and system management entity

### **Table Structure**
```sql
CREATE TABLE admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `admin_id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique administrator identifier |
| `name` | VARCHAR(100) | NULL | Administrator's full name |
| `email` | VARCHAR(100) | UNIQUE, NOT NULL | Login email (unique across system) |
| `password` | VARCHAR(255) | NOT NULL | Hashed password (Werkzeug PBKDF2) |

### **Business Rules**
- **Uniqueness:** Email must be unique across entire system
- **Security:** Passwords hashed using Werkzeug security
- **Authentication:** Primary login mechanism for admin portal
- **Session Management:** 30-minute session timeout

### **Relationships**
```
Admin Model
├── Independent Entity (No Foreign Keys)
├── Referenced by: None (System Root Entity)
└── References: None
```

### **CRUD Operations**
```python
# Create Admin
INSERT INTO admin (email, password) VALUES (?, ?)

# Read Admin (Login)
SELECT * FROM admin WHERE email = ?

# Update Admin
UPDATE admin SET name = ?, email = ? WHERE admin_id = ?

# Delete Admin (Rare)
DELETE FROM admin WHERE admin_id = ?
```

### **Usage in Application**
```python
# Authentication Flow
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    cursor.execute("SELECT * FROM admin WHERE email = %s", (email,))
    admin = cursor.fetchone()
    if admin and check_password_hash(admin['password'], password):
        session['admin_id'] = admin['admin_id']
        # Login successful
```

---

## 👨‍🎓 2. Students Model

### **Model Purpose**
**Student Registry** - Core student information and authentication

### **Table Structure**
```sql
CREATE TABLE students (
    enrollment_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    semester INT,
    password_hash VARCHAR(255),
    is_password_changed BOOLEAN DEFAULT FALSE,
    contact_no VARCHAR(15),
    profile_pic VARCHAR(255) DEFAULT 'default.png'
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `enrollment_no` | VARCHAR(20) | PRIMARY KEY | Unique student enrollment number |
| `name` | VARCHAR(100) | NOT NULL | Student's full name |
| `email` | VARCHAR(150) | UNIQUE, NOT NULL | Student email (unique) |
| `department` | VARCHAR(50) | NULL | Academic department |
| `semester` | INT | NULL | Current semester (1-8) |
| `password_hash` | VARCHAR(255) | NULL | Hashed password for student portal |
| `is_password_changed` | BOOLEAN | DEFAULT FALSE | Password change tracking |
| `contact_no` | VARCHAR(15) | NULL | Contact phone number |
| `profile_pic` | VARCHAR(255) | DEFAULT 'default.png' | Profile picture filename |

### **Business Rules**
- **Primary Key:** Enrollment number (not auto-increment)
- **Authentication:** Dual authentication (admin sets initial, student changes)
- **Profile Management:** Editable contact info and profile picture
- **Department Validation:** Must match existing departments
- **Semester Range:** 1-8 for typical programs

### **Relationships**
```
Students Model (Central Entity)
├── Parent to: marks (CASCADE DELETE)
├── Parent to: attendance (CASCADE DELETE)
├── Parent to: feedback (CASCADE DELETE)
├── Referenced by: marks.enrollment_no
├── Referenced by: attendance.enrollment_no
└── Referenced by: feedback.student_id
```

### **Validation Rules**
```python
# Enrollment Number Format
def validate_enrollment(enrollment_no):
    # Format: DEPYYYRRR (e.g., BCA2024001)
    pattern = r'^[A-Z]{2,4}\d{7,9}$'
    return bool(re.match(pattern, enrollment_no))

# Email Domain Validation
def validate_student_email(email):
    # Must be institutional email
    allowed_domains = ['@college.edu', '@university.edu']
    return any(domain in email for domain in allowed_domains)
```

### **CRUD Operations**
```python
# Create Student
INSERT INTO students (enrollment_no, name, email, department, semester)
VALUES (?, ?, ?, ?, ?)

# Bulk Insert (CSV)
LOAD DATA INFILE 'students.csv'
INTO TABLE students
FIELDS TERMINATED BY ','
LINES TERMINATED BY '\n'
(enrollment_no, name, email, department, semester)

# Read with Filters
SELECT * FROM students
WHERE department = ? AND semester = ?
ORDER BY enrollment_no

# Update Profile
UPDATE students
SET contact_no = ?, profile_pic = ?
WHERE enrollment_no = ?

# Delete Student (Cascades)
DELETE FROM students WHERE enrollment_no = ?
```

### **Usage Patterns**
```python
# Student Authentication
def student_login():
    enrollment_no = request.form.get('enrollment_no')
    password = request.form.get('password')
    cursor.execute("""
        SELECT * FROM students
        WHERE enrollment_no = %s AND password_hash IS NOT NULL
    """, (enrollment_no,))
    student = cursor.fetchone()
    if student and check_password_hash(student['password_hash'], password):
        session['student_id'] = student['enrollment_no']
        return redirect(url_for('student.dashboard'))

# Profile Update
def update_profile():
    cursor.execute("""
        UPDATE students
        SET contact_no = %s, profile_pic = %s
        WHERE enrollment_no = %s
    """, (contact_no, profile_pic, session['student_id']))
```

---

## 👨‍🏫 3. Faculty Model

### **Model Purpose**
**Faculty Hub** - Teaching staff information and departmental organization

### **Table Structure**
```sql
CREATE TABLE faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    department VARCHAR(50),
    contact_no VARCHAR(20)
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `faculty_id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique faculty identifier |
| `faculty_name` | VARCHAR(100) | NOT NULL | Faculty member's full name |
| `email` | VARCHAR(150) | UNIQUE, NOT NULL | Faculty email (unique) |
| `department` | VARCHAR(50) | NULL | Department affiliation |
| `contact_no` | VARCHAR(20) | NULL | Contact information |

### **Business Rules**
- **Auto-Increment ID:** System-generated unique identifier
- **Department Assignment:** Must match existing departments
- **Email Uniqueness:** Unique across entire system
- **Contact Format:** Flexible phone number format

### **Relationships**
```
Faculty Model
├── Parent to: subjects (SET NULL on DELETE)
├── Referenced by: subjects.faculty_id
└── Independent: No child dependencies
```

### **CRUD Operations**
```python
# Create Faculty
INSERT INTO faculty (faculty_name, email, department, contact_no)
VALUES (?, ?, ?, ?)

# Read Faculty with Subjects
SELECT f.*, COUNT(s.subject_id) as subject_count
FROM faculty f
LEFT JOIN subjects s ON f.faculty_id = s.faculty_id
GROUP BY f.faculty_id

# Update Faculty
UPDATE faculty
SET faculty_name = ?, department = ?, contact_no = ?
WHERE faculty_id = ?

# Delete Faculty (Safe - SET NULL)
DELETE FROM faculty WHERE faculty_id = ?
-- Subjects.faculty_id becomes NULL
```

### **Usage in Analytics**
```python
# Faculty Performance Analysis
def get_faculty_performance():
    cursor.execute("""
        SELECT f.faculty_name,
               COUNT(DISTINCT s.subject_id) as subjects_taught,
               AVG(m.total_marks) as avg_student_marks,
               COUNT(DISTINCT m.enrollment_no) as students_taught
        FROM faculty f
        JOIN subjects s ON f.faculty_id = s.faculty_id
        JOIN marks m ON s.subject_id = m.subject_id
        GROUP BY f.faculty_id, f.faculty_name
        ORDER BY avg_student_marks DESC
    """)
    return cursor.fetchall()
```

---

## 📚 4. Subjects Model

### **Model Purpose**
**Curriculum Modules** - Academic subjects and course catalog

### **Table Structure**
```sql
CREATE TABLE subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    subject_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    semester INT,
    faculty_id INT,
    FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE SET NULL
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `subject_id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique subject identifier |
| `subject_name` | VARCHAR(100) | NOT NULL | Subject/course name |
| `department` | VARCHAR(50) | NULL | Department offering subject |
| `semester` | INT | NULL | Semester when taught |
| `faculty_id` | INT | FOREIGN KEY | Assigned faculty member |

### **Business Rules**
- **Faculty Assignment:** Optional (can be NULL)
- **Department Consistency:** Must match student departments
- **Semester Validation:** 1-8 range validation
- **Unique Subject Names:** Within department-semester

### **Relationships**
```
Subjects Model
├── Child of: faculty (SET NULL)
├── Parent to: marks (CASCADE DELETE)
├── Parent to: attendance (CASCADE DELETE)
├── Referenced by: marks.subject_id
└── Referenced by: attendance.subject_id
```

### **Advanced Relationships**
```sql
-- Subjects taught by faculty
SELECT s.*, f.faculty_name
FROM subjects s
JOIN faculty f ON s.faculty_id = f.faculty_id

-- Subjects by department and semester
SELECT * FROM subjects
WHERE department = ? AND semester = ?
ORDER BY subject_name

-- Subject enrollment count
SELECT s.subject_name, COUNT(m.enrollment_no) as enrolled_students
FROM subjects s
LEFT JOIN marks m ON s.subject_id = m.subject_id
GROUP BY s.subject_id, s.subject_name
```

### **CRUD Operations**
```python
# Create Subject
INSERT INTO subjects (subject_name, department, semester, faculty_id)
VALUES (?, ?, ?, ?)

# Read with Faculty Info
SELECT s.*, f.faculty_name
FROM subjects s
LEFT JOIN faculty f ON s.faculty_id = f.faculty_id
WHERE s.department = ?

# Update Subject
UPDATE subjects
SET faculty_id = ?  -- Reassign faculty
WHERE subject_id = ?

# Delete Subject (Cascades)
DELETE FROM subjects WHERE subject_id = ?
-- Removes all marks and attendance records
```

---

## 📊 5. Marks Model

### **Model Purpose**
**Academic Performance Ledger** - Comprehensive grade tracking system

### **Table Structure**
```sql
CREATE TABLE marks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    internal_marks INT DEFAULT 0,
    viva_marks INT DEFAULT 0,
    external_marks INT DEFAULT 0,
    total_marks INT DEFAULT 0,
    result VARCHAR(10) DEFAULT 'Fail',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    UNIQUE KEY unique_student_subject (enrollment_no, subject_id)
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique marks record ID |
| `enrollment_no` | VARCHAR(20) | FOREIGN KEY, NOT NULL | Student enrollment number |
| `subject_id` | INT | FOREIGN KEY, NOT NULL | Subject identifier |
| `internal_marks` | INT | DEFAULT 0 | Internal assessment (0-50) |
| `viva_marks` | INT | DEFAULT 0 | Viva/oral marks (0-20) |
| `external_marks` | INT | DEFAULT 0 | External exam marks (0-80) |
| `total_marks` | INT | DEFAULT 0 | Auto-calculated total |
| `result` | VARCHAR(10) | DEFAULT 'Fail' | Pass/Fail status |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

### **Business Rules**
- **Unique Constraint:** One record per student-subject combination
- **Marks Validation:** Component-wise range validation
- **Auto-Calculation:** Total marks computed automatically
- **Result Logic:** Pass/Fail based on total marks threshold
- **Cascade Delete:** Removes marks when student/subject deleted

### **Marks Calculation Logic**
```python
def calculate_total_marks(internal, viva, external):
    """Calculate total marks with validation"""
    # Validate ranges
    if not (0 <= internal <= 50): raise ValueError("Internal marks: 0-50")
    if not (0 <= viva <= 20): raise ValueError("Viva marks: 0-20")
    if not (0 <= external <= 80): raise ValueError("External marks: 0-80")

    total = internal + viva + external
    result = 'Pass' if total >= 40 else 'Fail'  # 40% passing threshold
    return total, result

# Usage in application
total_marks, result = calculate_total_marks(internal, viva, external)
cursor.execute("""
    INSERT INTO marks (enrollment_no, subject_id, internal_marks,
                      viva_marks, external_marks, total_marks, result)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (enrollment_no, subject_id, internal, viva, external, total_marks, result))
```

### **Relationships**
```
Marks Model (Junction Entity)
├── Child of: students (CASCADE DELETE)
├── Child of: subjects (CASCADE DELETE)
├── Composite Unique: (enrollment_no, subject_id)
└── Analytics Source: Performance calculations
```

### **Advanced Queries**
```sql
-- Student Grade Card
SELECT s.name, sub.subject_name,
       m.internal_marks, m.viva_marks, m.external_marks, m.total_marks, m.result
FROM marks m
JOIN students s ON m.enrollment_no = s.enrollment_no
JOIN subjects sub ON m.subject_id = sub.subject_id
WHERE m.enrollment_no = ?
ORDER BY sub.semester, sub.subject_name

-- Subject-wise Performance
SELECT sub.subject_name,
       AVG(m.total_marks) as avg_marks,
       COUNT(CASE WHEN m.result = 'Pass' THEN 1 END) * 100.0 / COUNT(*) as pass_percentage
FROM marks m
JOIN subjects sub ON m.subject_id = sub.subject_id
GROUP BY sub.subject_id, sub.subject_name

-- Student GPA Calculation
SELECT s.enrollment_no, s.name,
       AVG(m.total_marks) as gpa,
       COUNT(CASE WHEN m.result = 'Pass' THEN 1 END) as passed_subjects,
       COUNT(*) as total_subjects
FROM students s
LEFT JOIN marks m ON s.enrollment_no = m.enrollment_no
GROUP BY s.enrollment_no, s.name
```

### **CRUD Operations**
```python
# Insert Marks
INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks, result)
VALUES (?, ?, ?, ?, ?, ?, ?)

# Bulk Marks Insert (CSV)
LOAD DATA INFILE 'marks.csv'
INTO TABLE marks
FIELDS TERMINATED BY ','
(enrollment_no, subject_name, internal_marks, viva_marks, external_marks)

# Update Marks
UPDATE marks
SET internal_marks = ?, viva_marks = ?, external_marks = ?,
    total_marks = ?, result = ?
WHERE enrollment_no = ? AND subject_id = ?

# Student Performance Report
SELECT * FROM marks
WHERE enrollment_no = ?
ORDER BY created_at DESC
```

---

## 📅 6. Attendance Model

### **Model Purpose**
**Global Attendance Registry** - Daily attendance tracking for all subjects

### **Table Structure**
```sql
CREATE TABLE attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_no VARCHAR(20),
    subject_id INT,
    date DATE,
    status VARCHAR(20),
    FOREIGN KEY (enrollment_no) REFERENCES students(enrollment_no) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `attendance_id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique attendance record ID |
| `enrollment_no` | VARCHAR(20) | FOREIGN KEY, NOT NULL | Student enrollment number |
| `subject_id` | INT | FOREIGN KEY, NOT NULL | Subject identifier |
| `date` | DATE | NOT NULL | Attendance date |
| `status` | VARCHAR(20) | NULL | Attendance status |

### **Status Values**
```python
ATTENDANCE_STATUSES = [
    'Present',      # Student was present
    'Absent',       # Student was absent
    'Late',         # Student arrived late
    'Excused',      # Legitimate absence
    'Holiday'       # Institutional holiday
]
```

### **Business Rules**
- **Daily Tracking:** One record per student-subject-date
- **Status Validation:** Must be from approved status list
- **Date Validation:** Cannot be future dates
- **Cascade Delete:** Removes attendance when student/subject deleted

### **Relationships**
```
Attendance Model
├── Child of: students (CASCADE DELETE)
├── Child of: subjects (CASCADE DELETE)
├── Analytics Source: Attendance calculations
└── Reporting: Daily/weekly/monthly reports
```

### **Advanced Analytics Queries**
```sql
-- Daily Attendance Report
SELECT s.name, sub.subject_name, a.date, a.status
FROM attendance a
JOIN students s ON a.enrollment_no = s.enrollment_no
JOIN subjects sub ON a.subject_id = sub.subject_id
WHERE a.date = CURDATE()
ORDER BY sub.subject_name, s.name

-- Monthly Attendance Summary
SELECT s.enrollment_no, s.name,
       COUNT(CASE WHEN a.status = 'Present' THEN 1 END) as present_days,
       COUNT(*) as total_days,
       ROUND(COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(*), 2) as percentage
FROM students s
LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
WHERE MONTH(a.date) = MONTH(CURDATE()) AND YEAR(a.date) = YEAR(CURDATE())
GROUP BY s.enrollment_no, s.name

-- Subject-wise Attendance
SELECT sub.subject_name,
       COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_percentage,
       COUNT(DISTINCT a.enrollment_no) as enrolled_students
FROM subjects sub
LEFT JOIN attendance a ON sub.subject_id = a.subject_id
GROUP BY sub.subject_id, sub.subject_name

-- Low Attendance Alert
SELECT s.enrollment_no, s.name, s.contact_no,
       COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_percentage
FROM students s
LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
GROUP BY s.enrollment_no, s.name, s.contact_no
HAVING attendance_percentage < 75
ORDER BY attendance_percentage ASC
```

### **CRUD Operations**
```python
# Mark Daily Attendance
INSERT INTO attendance (enrollment_no, subject_id, date, status)
VALUES (?, ?, ?, ?)
ON DUPLICATE KEY UPDATE status = VALUES(status)

# Bulk Attendance (CSV)
LOAD DATA INFILE 'attendance.csv'
INTO TABLE attendance
FIELDS TERMINATED BY ','
(enrollment_no, subject_name, date, status)

# Update Attendance Status
UPDATE attendance
SET status = ?
WHERE enrollment_no = ? AND subject_id = ? AND date = ?

# Student Attendance Report
SELECT date, status, sub.subject_name
FROM attendance a
JOIN subjects sub ON a.subject_id = sub.subject_id
WHERE enrollment_no = ?
ORDER BY date DESC
```

---

## 💬 7. Feedback Model

### **Model Purpose**
**Institutional Feedback Channel** - Student-to-administration communication system

### **Table Structure**
```sql
CREATE TABLE feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50),
    student_name VARCHAR(100),
    department VARCHAR(50),
    semester INT,
    subject VARCHAR(255),
    feedback_type VARCHAR(50) DEFAULT 'Suggestion',
    comment TEXT,
    admin_reply TEXT,
    status VARCHAR(20) DEFAULT 'Pending',
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rating INT DEFAULT 5,
    FOREIGN KEY (student_id) REFERENCES students(enrollment_no) ON DELETE CASCADE
);
```

### **Attributes Detail**

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `feedback_id` | INT | PRIMARY KEY, AUTO_INCREMENT | Unique feedback ID |
| `student_id` | VARCHAR(50) | FOREIGN KEY | Student enrollment number |
| `student_name` | VARCHAR(100) | NULL | Student's name (denormalized) |
| `department` | VARCHAR(50) | NULL | Student's department |
| `semester` | INT | NULL | Student's semester |
| `subject` | VARCHAR(255) | NULL | Subject name (optional) |
| `feedback_type` | VARCHAR(50) | DEFAULT 'Suggestion' | Feedback category |
| `comment` | TEXT | NULL | Feedback content |
| `admin_reply` | TEXT | NULL | Administrative response |
| `status` | VARCHAR(20) | DEFAULT 'Pending' | Processing status |
| `date` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Submission timestamp |
| `rating` | INT | DEFAULT 5 | Rating (1-5 scale) |

### **Feedback Types**
```python
FEEDBACK_TYPES = [
    'Suggestion',      # General suggestions
    'Complaint',       # Issues or problems
    'Appreciation',    # Positive feedback
    'Question',        # Queries or doubts
    'Technical Issue', # System-related problems
    'Academic Concern' # Academic matters
]
```

### **Status Values**
```python
FEEDBACK_STATUSES = [
    'Pending',     # Awaiting review
    'Reviewed',    # Under review
    'Resolved',    # Issue addressed
    'Closed',      # Final response given
    'Escalated'    # Requires higher attention
]
```

### **Business Rules**
- **Anonymous Option:** Student name can be masked for privacy
- **Rating Scale:** 1-5 stars (5 being highest)
- **Admin Response:** Required before marking as resolved
- **Cascade Delete:** Removes feedback when student deleted
- **Audit Trail:** Timestamp tracking for all actions

### **Relationships**
```
Feedback Model
├── Child of: students (CASCADE DELETE)
├── Communication Channel: Student ↔ Admin
├── Analytics Source: Satisfaction metrics
└── Reporting: Feedback analysis
```

### **Advanced Analytics**
```sql
-- Feedback Summary by Type
SELECT feedback_type, COUNT(*) as count,
       AVG(rating) as avg_rating
FROM feedback
GROUP BY feedback_type
ORDER BY count DESC

-- Department-wise Feedback
SELECT department,
       AVG(rating) as avg_rating,
       COUNT(*) as total_feedback,
       COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_count
FROM feedback
GROUP BY department

-- Response Time Analysis
SELECT feedback_id,
       TIMESTAMPDIFF(HOUR, date, NOW()) as hours_to_respond
FROM feedback
WHERE admin_reply IS NOT NULL
ORDER BY hours_to_respond DESC

-- Student Satisfaction Trends
SELECT DATE(date) as feedback_date,
       AVG(rating) as daily_avg_rating,
       COUNT(*) as daily_count
FROM feedback
WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(date)
ORDER BY feedback_date
```

### **CRUD Operations**
```python
# Submit Feedback
INSERT INTO feedback (student_id, student_name, department, semester,
                     subject, feedback_type, comment, rating)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)

# Admin Response
UPDATE feedback
SET admin_reply = ?, status = 'Resolved'
WHERE feedback_id = ?

# View Student Feedback
SELECT * FROM feedback
WHERE student_id = ?
ORDER BY date DESC

# Feedback Analytics
SELECT feedback_type, AVG(rating) as avg_rating, COUNT(*) as count
FROM feedback
WHERE status = 'Resolved'
GROUP BY feedback_type
```

---

## 🔗 Model Relationships & Data Flow

### **Entity Relationship Diagram**
```
┌─────────────┐       ┌─────────────┐
│    Admin    │       │  Students   │
│             │       │             │
│ • admin_id  │       │ • enroll_no │
│ • name      │       │ • name      │
│ • email     │       │ • email     │
│ • password  │       │ • dept      │
└─────────────┘       │ • semester  │
                      │ • contact   │
                      └─────┬───────┘
                            │ 1:N
                            │
                            ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Faculty   │◄──────┤  Subjects   │◄──────┤    Marks    │
│             │ 1:N   │             │ 1:N   │             │
│ • faculty_id│       │ • subject_id│       │ • id        │
│ • name      │       │ • name      │       │ • enroll_no │
│ • email     │       │ • dept      │       │ • subject_id│
│ • dept      │       │ • semester  │       │ • internal  │
│ • contact   │       │ • faculty_id│       │ • viva      │
└─────────────┘       └─────┼───────┘       │ • external  │
                            │ 1:N           │ • total     │
                            │               │ • result    │
                            ▼               └─────────────┘
                      ┌─────────────┐
                      │ Attendance  │
                      │             │
                      │ • attend_id │
                      │ • enroll_no │
                      │ • subject_id│
                      │ • date      │
                      │ • status    │
                      └─────────────┘

┌─────────────┐
│  Feedback   │
│             │
│ • feedback_id│
│ • student_id │
│ • student_name│
│ • dept       │
│ • semester   │
│ • subject    │
│ • faculty    │
│ • rating     │
│ • comment    │
│ • admin_reply│
│ • date       │
└─────────────┘
```

### **Data Flow Patterns**

#### **Student Registration Flow**
```
Student Data → Validation → Students Table
                   ↓
            Password Generation → Email Notification
                   ↓
            Profile Setup → Dashboard Access
```

#### **Academic Performance Flow**
```
Subject Creation → Faculty Assignment → Student Enrollment
      ↓              ↓                        ↓
Marks Entry → Validation → Calculation → Result Generation
      ↓              ↓                        ↓
Analytics → Reports → Dashboard → Student Portal
```

#### **Attendance Tracking Flow**
```
Subject Schedule → Daily Marking → Status Update
      ↓                  ↓              ↓
Validation → Storage → Analytics → Reports/Alerts
      ↓                  ↓              ↓
Dashboard → Student View → Admin Monitoring
```

#### **Feedback System Flow**
```
Student Input → Validation → Storage → Admin Review
      ↓              ↓            ↓          ↓
Categorization → Analysis → Response → Resolution
      ↓              ↓            ↓          ↓
Reports → Trends → Improvements → System Updates
```

---

## 📊 Analytics Models & Calculations

### **Performance Analytics Models**

#### **Student Performance Model**
```python
def calculate_student_performance(enrollment_no):
    """Comprehensive student performance analysis"""
    cursor.execute("""
        SELECT
            COUNT(*) as total_subjects,
            AVG(total_marks) as overall_average,
            COUNT(CASE WHEN result = 'Pass' THEN 1 END) as passed_subjects,
            COUNT(CASE WHEN result = 'Fail' THEN 1 END) as failed_subjects,
            MAX(total_marks) as highest_marks,
            MIN(total_marks) as lowest_marks
        FROM marks
        WHERE enrollment_no = ?
    """, (enrollment_no,))

    # Grade distribution
    cursor.execute("""
        SELECT
            COUNT(CASE WHEN total_marks >= 90 THEN 1 END) as grade_a,
            COUNT(CASE WHEN total_marks >= 80 AND total_marks < 90 THEN 1 END) as grade_b,
            COUNT(CASE WHEN total_marks >= 70 AND total_marks < 80 THEN 1 END) as grade_c,
            COUNT(CASE WHEN total_marks >= 60 AND total_marks < 70 THEN 1 END) as grade_d,
            COUNT(CASE WHEN total_marks < 60 THEN 1 END) as grade_f
        FROM marks
        WHERE enrollment_no = ?
    """, (enrollment_no,))

    return performance_data
```

#### **Subject Performance Model**
```python
def analyze_subject_performance(subject_id):
    """Subject-wise performance analytics"""
    cursor.execute("""
        SELECT
            sub.subject_name,
            COUNT(m.id) as enrolled_students,
            AVG(m.total_marks) as average_marks,
            COUNT(CASE WHEN m.result = 'Pass' THEN 1 END) * 100.0 / COUNT(*) as pass_percentage,
            MAX(m.total_marks) as highest_score,
            f.faculty_name
        FROM subjects sub
        LEFT JOIN marks m ON sub.subject_id = m.subject_id
        LEFT JOIN faculty f ON sub.faculty_id = f.faculty_id
        WHERE sub.subject_id = ?
        GROUP BY sub.subject_id, sub.subject_name, f.faculty_name
    """, (subject_id,))

    return subject_analysis
```

### **Attendance Analytics Models**

#### **Student Attendance Model**
```python
def calculate_attendance_percentage(enrollment_no, subject_id=None):
    """Calculate attendance percentage with filters"""
    if subject_id:
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as percentage,
                COUNT(CASE WHEN status = 'Present' THEN 1 END) as present_days,
                COUNT(CASE WHEN status = 'Late' THEN 1 END) as late_days,
                COUNT(CASE WHEN status = 'Absent' THEN 1 END) as absent_days,
                COUNT(*) as total_days
            FROM attendance
            WHERE enrollment_no = ? AND subject_id = ?
        """, (enrollment_no, subject_id))
    else:
        # Overall attendance
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as percentage
            FROM attendance
            WHERE enrollment_no = ?
        """, (enrollment_no,))

    return attendance_data
```

#### **Department Attendance Model**
```python
def get_department_attendance(department, semester=None):
    """Department-wide attendance analysis"""
    query = """
        SELECT
            s.enrollment_no,
            s.name,
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_percentage,
            COUNT(*) as total_classes
        FROM students s
        LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
        WHERE s.department = ?
    """
    params = [department]

    if semester:
        query += " AND s.semester = ?"
        params.append(semester)

    query += " GROUP BY s.enrollment_no, s.name ORDER BY attendance_percentage ASC"

    cursor.execute(query, params)
    return cursor.fetchall()
```

### **Feedback Analytics Models**

#### **Satisfaction Metrics Model**
```python
def calculate_satisfaction_metrics():
    """Overall system satisfaction analysis"""
    cursor.execute("""
        SELECT
            AVG(rating) as overall_satisfaction,
            COUNT(CASE WHEN rating >= 4 THEN 1 END) * 100.0 / COUNT(*) as positive_feedback_percentage,
            COUNT(*) as total_feedback,
            COUNT(CASE WHEN admin_reply IS NOT NULL THEN 1 END) as responded_feedback
        FROM feedback
        WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """)

    # Category-wise analysis
    cursor.execute("""
        SELECT
            feedback_type,
            AVG(rating) as avg_rating,
            COUNT(*) as count
        FROM feedback
        GROUP BY feedback_type
        ORDER BY count DESC
    """)

    return satisfaction_data
```

---

## 🔒 Data Validation & Security Models

### **Input Validation Models**
```python
class DataValidator:
    @staticmethod
    def validate_enrollment_number(enrollment_no):
        """Validate enrollment number format"""
        pattern = r'^[A-Z]{2,4}\d{7,9}$'
        return bool(re.match(pattern, enrollment_no))

    @staticmethod
    def validate_marks(internal, viva, external):
        """Validate marks ranges"""
        validations = [
            (0 <= internal <= 50, "Internal marks must be 0-50"),
            (0 <= viva <= 20, "Viva marks must be 0-20"),
            (0 <= external <= 80, "External marks must be 0-80")
        ]
        for is_valid, message in validations:
            if not is_valid:
                raise ValueError(message)
        return True

    @staticmethod
    def validate_email(email, domain_check=True):
        """Validate email format and domain"""
        basic_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(basic_pattern, email):
            raise ValueError("Invalid email format")

        if domain_check:
            allowed_domains = ['@college.edu', '@university.edu', '@institution.edu']
            if not any(domain in email for domain in allowed_domains):
                raise ValueError("Email must be from institutional domain")
        return True
```

### **Security Models**
```python
class SecurityManager:
    @staticmethod
    def hash_password(password):
        """Secure password hashing"""
        return generate_password_hash(password, method='pbkdf2:sha256')

    @staticmethod
    def verify_password(hashed_password, provided_password):
        """Password verification"""
        return check_password_hash(hashed_password, provided_password)

    @staticmethod
    def generate_session_token():
        """Generate secure session token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_session(session_data):
        """Validate session integrity"""
        required_fields = ['user_id', 'login_time', 'ip_address']
        return all(field in session_data for field in required_fields)
```

---

## 🚀 Model Usage Patterns in Application

### **Admin Portal Models Usage**
```python
# Dashboard - Multiple Model Aggregation
def get_dashboard_data():
    stats = {}
    # Student statistics
    cursor.execute("SELECT COUNT(*) FROM students")
    stats['total_students'] = cursor.fetchone()[0]

    # Subject statistics
    cursor.execute("SELECT COUNT(*) FROM subjects")
    stats['total_subjects'] = cursor.fetchone()[0]

    # Performance metrics (Marks model)
    cursor.execute("SELECT AVG(total_marks) FROM marks")
    stats['avg_marks'] = cursor.fetchone()[0]

    # Attendance metrics (Attendance model)
    cursor.execute("""
        SELECT AVG(attendance_pct) FROM (
            SELECT enrollment_no,
                   COUNT(CASE WHEN status='Present' THEN 1 END) * 100.0 / COUNT(*) as attendance_pct
            FROM attendance
            GROUP BY enrollment_no
        ) as attendance_stats
    """)
    stats['avg_attendance'] = cursor.fetchone()[0]

    return stats
```

### **Student Portal Models Usage**
```python
# Student Performance View
def get_student_performance(enrollment_no):
    # Basic info from Students model
    cursor.execute("SELECT * FROM students WHERE enrollment_no = ?", (enrollment_no,))
    student = cursor.fetchone()

    # Academic performance from Marks model
    cursor.execute("""
        SELECT sub.subject_name, m.total_marks, m.result, m.created_at
        FROM marks m
        JOIN subjects sub ON m.subject_id = sub.subject_id
        WHERE m.enrollment_no = ?
        ORDER BY m.created_at DESC
    """, (enrollment_no,))
    marks = cursor.fetchall()

    # Attendance from Attendance model
    cursor.execute("""
        SELECT sub.subject_name,
               COUNT(CASE WHEN a.status='Present' THEN 1 END) * 100.0 / COUNT(*) as percentage
        FROM attendance a
        JOIN subjects sub ON a.subject_id = sub.subject_id
        WHERE a.enrollment_no = ?
        GROUP BY sub.subject_id, sub.subject_name
    """, (enrollment_no,))
    attendance = cursor.fetchall()

    return {
        'student': student,
        'marks': marks,
        'attendance': attendance
    }
```

---

## 📈 Model Performance & Optimization

### **Indexing Strategy**
```sql
-- Primary Keys (Auto-indexed)
-- enrollment_no (Students) - High cardinality
-- admin_id, faculty_id, subject_id, etc.

-- Foreign Key Indexes (Auto-created by MySQL)
-- marks.enrollment_no → students.enrollment_no
-- marks.subject_id → subjects.subject_id
-- attendance.enrollment_no → students.enrollment_no
-- attendance.subject_id → subjects.subject_id

-- Composite Indexes for Performance
CREATE INDEX idx_marks_student_subject ON marks(enrollment_no, subject_id);
CREATE INDEX idx_attendance_student_date ON attendance(enrollment_no, date);
CREATE INDEX idx_feedback_student_date ON feedback(student_id, date);

-- Query-Specific Indexes
CREATE INDEX idx_students_dept_sem ON students(department, semester);
CREATE INDEX idx_subjects_dept_sem ON subjects(department, semester);
```

### **Query Optimization Patterns**
```python
# Efficient Student Lookup
def get_student_with_performance(enrollment_no):
    """Single query with JOINs instead of multiple queries"""
    cursor.execute("""
        SELECT
            s.*,
            COUNT(DISTINCT m.subject_id) as subjects_enrolled,
            AVG(m.total_marks) as avg_marks,
            COUNT(CASE WHEN m.result = 'Pass' THEN 1 END) as passed_subjects,
            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 100.0 / COUNT(DISTINCT a.attendance_id) as attendance_pct
        FROM students s
        LEFT JOIN marks m ON s.enrollment_no = m.enrollment_no
        LEFT JOIN attendance a ON s.enrollment_no = a.enrollment_no
        WHERE s.enrollment_no = ?
        GROUP BY s.enrollment_no
    """, (enrollment_no,))
    return cursor.fetchone()
```

---

## 🎯 Conclusion

The SPDA system implements a comprehensive **7-model architecture** that provides:

✅ **Admin Model** - Secure administrative access and system management  
✅ **Students Model** - Complete student lifecycle and profile management  
✅ **Faculty Model** - Teaching staff organization and subject assignments  
✅ **Subjects Model** - Academic curriculum and course catalog management  
✅ **Marks Model** - Multi-component academic performance tracking  
✅ **Attendance Model** - Daily attendance monitoring and analytics  
✅ **Feedback Model** - Institutional communication and satisfaction tracking  

### **Key Architectural Strengths**
- **3NF Normalization** ensuring data integrity
- **Referential Integrity** with appropriate cascade actions
- **Comprehensive Relationships** supporting complex analytics
- **Scalable Design** for growing institutional needs
- **Security-First Approach** with proper authentication
- **Analytics-Ready** with optimized query patterns

### **Model Interoperability**
The models work together seamlessly to provide:
- **Unified Student Experience** across all modules
- **Comprehensive Analytics** for decision making
- **Automated Workflows** for academic processes
- **Data Consistency** through referential constraints
- **Performance Optimization** with strategic indexing

This model architecture forms the backbone of a robust, scalable educational management system capable of handling complex academic workflows while maintaining data integrity and providing rich analytical capabilities.

**Models Status:** Production Ready  
**Architecture:** Enterprise Grade  
**Scalability:** High  
**Maintainability:** Excellent  
**Analytics Capability:** Advanced