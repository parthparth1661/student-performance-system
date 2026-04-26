import csv
import os
from db import get_db_connection

def import_all():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Clear existing data safely
    print("Clearing old data...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE attendance;")
    cursor.execute("TRUNCATE TABLE marks;")
    cursor.execute("TRUNCATE TABLE students;")
    cursor.execute("TRUNCATE TABLE subjects;")
    cursor.execute("TRUNCATE TABLE faculty;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()

    base_dir = 'dataset_csv'
    
    # 2. Insert Faculty
    print("Importing faculty...")
    with open(os.path.join(base_dir, 'faculty.csv'), 'r') as f:
        reader = csv.DictReader(f)
        faculty_data = [(r['faculty_id'], r['faculty_name'], r['email'], r['department'], r['contact_no']) for r in reader]
    cursor.executemany("INSERT INTO faculty (faculty_id, faculty_name, email, department, contact_no) VALUES (%s, %s, %s, %s, %s)", faculty_data)
    conn.commit()

    # 3. Insert Subjects
    print("Importing subjects...")
    cursor.execute("SELECT faculty_name, faculty_id FROM faculty")
    faculty_lookup = {row[0]: row[1] for row in cursor.fetchall()}
    with open(os.path.join(base_dir, 'subjects.csv'), 'r') as f:
        reader = csv.DictReader(f)
        subj_data = [(r['subject_id'], r['subject_name'], r['department'], r['semester'], faculty_lookup.get(r['faculty_name'])) for r in reader]
    cursor.executemany("INSERT INTO subjects (subject_id, subject_name, department, semester, faculty_id) VALUES (%s, %s, %s, %s, %s)", subj_data)
    conn.commit()
    
    # 4. Insert Students
    print("Importing students...")
    with open(os.path.join(base_dir, 'students.csv'), 'r') as f:
        reader = csv.DictReader(f)
        stu_data = [(r['enrollment_no'], r['name'], r['email'], r['department'], r['semester']) for r in reader]
    cursor.executemany("INSERT INTO students (enrollment_no, name, email, department, semester) VALUES (%s, %s, %s, %s, %s)", stu_data)
    conn.commit()

    # 5. Insert Marks
    print("Importing marks...")
    cursor.execute("SELECT subject_id, subject_name FROM subjects")
    subject_lookup = {row[1]: row[0] for row in cursor.fetchall()}
    with open(os.path.join(base_dir, 'marks.csv'), 'r') as f:
        reader = csv.DictReader(f)
        marks_data = []
        for r in reader:
            s_id = subject_lookup.get(r['subject_name'])
            total = int(r['internal_marks']) + int(r['viva_marks']) + int(r['external_marks'])
            marks_data.append((r['enrollment_no'], s_id, r['internal_marks'], r['viva_marks'], r['external_marks'], total))
    cursor.executemany("INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks) VALUES (%s, %s, %s, %s, %s, %s)", marks_data)
    conn.commit()

    # 6. Insert Attendance
    print("Importing attendance...")
    with open(os.path.join(base_dir, 'attendance.csv'), 'r') as f:
        reader = csv.DictReader(f)
        att_data = [(r['enrollment_no'], r['subject_id'], r['date'], r['status']) for r in reader]
    
    # Chunk attendance insert
    chunk_size = 5000
    for i in range(0, len(att_data), chunk_size):
        chunk = att_data[i:i+chunk_size]
        cursor.executemany("INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s, %s, %s, %s)", chunk)
    conn.commit()

    cursor.close()
    conn.close()
    print("Bulk import completed successfully!")

if __name__ == '__main__':
    import_all()
