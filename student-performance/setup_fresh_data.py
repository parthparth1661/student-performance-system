import os
import glob
import pandas as pd
import random
from datetime import date, timedelta, datetime
from db import get_db_connection
from werkzeug.security import generate_password_hash

# --- Configuration ---
DEPARTMENTS = ['BCA', 'MCA', 'BTECH', 'MBA']
SEMESTERS = ['Semester 1', 'Semester 2']
STUDENTS_PER_BATCH = 15
TOTAL_STUDENTS = len(DEPARTMENTS) * len(SEMESTERS) * STUDENTS_PER_BATCH

SUBJECTS = {
    'BCA': ['Python Programming', 'DBMS', 'Data Structures', 'Web Technology', 'Operating Systems', 'Mathematics'],
    'MCA': ['Advanced Python', 'DSA', 'Cloud Computing', 'Machine Learning', 'Software Engineering', 'Research Methods'],
    'BTECH': ['Engineering Maths', 'DBMS', 'OS', 'Networks', 'Data Structures', 'Software Engineering'],
    'MBA': ['Marketing', 'Finance', 'HRM', 'Operations', 'Business Analytics', 'Strategic Management']
}

EXAM_DATES = {
    'Internal': '2026-02-05',
    'Practical': '2026-02-15',
    'External': '2026-03-10'
}

TERM_DATES = {
    'Semester 1': (date(2026, 1, 1), date(2026, 4, 30)),
    'Semester 2': (date(2026, 7, 1), date(2026, 10, 30))
}

INDIAN_NAMES_FIRST = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Diya", "Saanvi", "Anya", "Aadhya", "Pari", "Ananya", "Myra", "Riya", "Meera", "Isha",
    "Rohan", "Vikram", "Rahul", "Sneha", "Pooja", "Amit", "Suresh", "Priya", "Neha", "Karan",
    "Manish", "Ramesh", "Sita", "Gita", "Lakshmi", "Raj", "Rani", "Vijay", "Anil", "Sunil"
]

INDIAN_NAMES_LAST = [
    "Patel", "Sharma", "Singh", "Kumar", "Gupta", "Mehta", "Jain", "Shah", "Agarwal", "Verma",
    "Mishra", "Reddy", "Nair", "Iyer", "Patil", "Desai", "Joshi", "Chauhan", "Rathod", "Das"
]

# --- 1. CLEANUP FILES ---
def cleanup_files():
    print("--- 1. Cleaning Old Files ---")
    patterns = [
        '*.csv', # Root directory CSVs
        'uploads/*.csv', 
        'static/uploads/*.csv', 
        'static/charts/*.png',
        'static/charts/*.jpg'
    ]
    for pattern in patterns:
        files = glob.glob(pattern)
        for f in files:
            try:
                os.remove(f)
                print(f"Deleted: {f}")
            except Exception as e:
                print(f"Error deleting {f}: {e}")

# --- 2. RESET DATABASE ---
def reset_database():
    print("\n--- 2. Resetting Database ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("TRUNCATE TABLE attendance;")
        cursor.execute("TRUNCATE TABLE marks;")
        cursor.execute("TRUNCATE TABLE students;")
        cursor.execute("TRUNCATE TABLE academic_calendar;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        print("Database Truncated Successfully.")
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        cursor.close()
        conn.close()

# --- 3. GENERATE DATASETS ---
def generate_datasets():
    print("\n--- 3. Generating Fresh Real-World Datasets ---")
    
    # 3.1 STUDENTS
    students_data = []
    
    # Roll counters per dept/sem to make them look distinct
    # e.g. BCA101..., MCA201...
    
    for dept in DEPARTMENTS:
        for sem in SEMESTERS:
            # Base roll number: e.g. BCA + 1 (for sem1) + 01
            sem_digit = sem[-1]
            roll_prefix = f"{dept}{sem_digit}"
            
            for i in range(1, STUDENTS_PER_BATCH + 1):
                roll_no = f"{roll_prefix}{i:03d}" # e.g. BCA1001
                
                fname = random.choice(INDIAN_NAMES_FIRST)
                lname = random.choice(INDIAN_NAMES_LAST)
                name = f"{fname} {lname}"
                
                # Professional email
                email = f"{fname.lower()}.{lname.lower()}{random.randint(10,99)}@example.com"
                
                students_data.append({
                    'roll_no': roll_no,
                    'name': name,
                    'email': email,
                    'department': dept,
                    'semester': sem
                })
                
    df_students = pd.DataFrame(students_data)
    df_students.to_csv('students.csv', index=False)
    print(f"Generated students.csv ({len(df_students)} records)")

    # 3.2 MARKS
    marks_data = []
    
    for s in students_data:
        dept = s['department']
        subjects = SUBJECTS.get(dept, [])
        
        # Determine performance profile: 60% Avg, 20% High, 20% Weak
        profile = random.choices(['average', 'high', 'weak'], weights=[0.6, 0.2, 0.2])[0]
        
        for sub in subjects:
            for exam_type, exam_date in EXAM_DATES.items():
                # Skip Practical for MBA
                if dept == 'MBA' and exam_type == 'Practical':
                    continue
                    
                # Generate Marks
                if profile == 'average':
                    marks = random.randint(50, 80)
                elif profile == 'high':
                    marks = random.randint(85, 95)
                else: # weak
                    marks = random.randint(20, 40)
                    
                marks_data.append({
                    'roll_no': s['roll_no'],
                    'subject': sub,
                    'marks': marks,
                    'exam_type': exam_type,
                    'exam_date': exam_date
                })
                
    df_marks = pd.DataFrame(marks_data)
    df_marks.to_csv('marks.csv', index=False)
    print(f"Generated marks.csv ({len(df_marks)} records)")

    # 3.3 ATTENDANCE
    attendance_data = []
    
    for s in students_data:
        sem = s['semester']
        start_date, end_date = TERM_DATES[sem]
        
        # Determine attendance profile
        # Majority 75-90%, Some <75%, Few >95%
        profile = random.choices(['average', 'low', 'high'], weights=[0.7, 0.2, 0.1])[0]
        
        current_date = start_date
        while current_date <= end_date:
            # Skip Sundays
            if current_date.weekday() == 6:
                current_date += timedelta(days=1)
                continue
                
            # Status probability
            if profile == 'average':
                # 75-90% means 10-25% absent
                status = 'Present' if random.random() < 0.85 else 'Absent'
            elif profile == 'low':
                # <75%
                status = 'Present' if random.random() < 0.60 else 'Absent'
            else: # high
                # >95%
                status = 'Present' if random.random() < 0.98 else 'Absent'
            
            remarks = ""
            if status == 'Absent':
                remarks = random.choice(['Fever', 'Medical Leave', 'Family Function', 'Personal Work', 'Sick'])
                
            attendance_data.append({
                'roll_no': s['roll_no'],
                'attendance_date': current_date.strftime('%Y-%m-%d'),
                'status': status,
                'remarks': remarks
            })
            
            current_date += timedelta(days=1)
            
    df_attendance = pd.DataFrame(attendance_data)
    df_attendance.to_csv('attendance.csv', index=False)
    print(f"Generated attendance.csv ({len(df_attendance)} records)")

# --- 4. IMPORT TO DATABASE ---
def import_data():
    print("\n--- 4. Importing Data to Database ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 4.1 Populate Academic Calendar
        print("Importing Academic Calendar...")
        for dept in DEPARTMENTS:
            for sem in SEMESTERS:
                start, end = TERM_DATES[sem]
                cursor.execute("""
                    INSERT INTO academic_calendar (department, semester, start_date, end_date)
                    VALUES (%s, %s, %s, %s)
                """, (dept, sem, start, end))
        conn.commit()
        
        # 4.2 Import Students
        print("Importing Students...")
        df_students = pd.read_csv('students.csv').fillna('')
        for _, row in df_students.iterrows():
            default_pw = f"{row['roll_no']}@123"
            pw_hash = generate_password_hash(default_pw)
            cursor.execute("""
                INSERT INTO students (roll_no, name, email, department, semester, password_hash, is_password_changed)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
            """, (row['roll_no'], row['name'], row['email'], row['department'], row['semester'], pw_hash))
        conn.commit()
        
        # Cache Student IDs
        cursor.execute("SELECT roll_no, student_id FROM students")
        student_map = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 4.3 Import Marks
        print("Importing Marks...")
        df_marks = pd.read_csv('marks.csv').fillna('')
        marks_values = []
        for _, row in df_marks.iterrows():
            sid = student_map.get(row['roll_no'])
            if sid:
                marks_values.append((sid, row['subject'], row['marks'], row['exam_type'], row['exam_date']))
        
        if marks_values:
            cursor.executemany("""
                INSERT INTO marks (student_id, subject, marks, exam_type, exam_date)
                VALUES (%s, %s, %s, %s, %s)
            """, marks_values)
            conn.commit()
            
        # 4.4 Import Attendance
        print("Importing Attendance (this might take a moment)...")
        df_attendance = pd.read_csv('attendance.csv').fillna('')
        
        # Batch insert for performance
        batch_size = 1000
        attendance_values = []
        
        for _, row in df_attendance.iterrows():
            sid = student_map.get(row['roll_no'])
            if sid:
                attendance_values.append((sid, row['attendance_date'], row['status'], row['remarks']))
                
            if len(attendance_values) >= batch_size:
                cursor.executemany("""
                    INSERT INTO attendance (student_id, attendance_date, status, remarks)
                    VALUES (%s, %s, %s, %s)
                """, attendance_values)
                conn.commit()
                attendance_values = []
                
        if attendance_values:
            cursor.executemany("""
                INSERT INTO attendance (student_id, attendance_date, status, remarks)
                VALUES (%s, %s, %s, %s)
            """, attendance_values)
            conn.commit()
            
        print("Data Import Complete!")
        
    except Exception as e:
        print(f"Import Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    cleanup_files()
    reset_database()
    generate_datasets()
    import_data()
    print("\n--- DONE ---")
