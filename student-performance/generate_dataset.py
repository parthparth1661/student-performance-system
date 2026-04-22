import csv
import os
import random
from datetime import datetime, timedelta

# Configuration
DEPARTMENTS = {
    'BCA': range(1, 7),
    'MCA': range(1, 5),
    'BBA': range(1, 7),
    'MBA': range(1, 5)
}

STUDENTS_PER_SEM = 30
FACULTY_PER_DEPT = 3
SUBJECTS_PER_SEM = 4
START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 3, 31)

OUTPUT_DIR = 'dataset_csv'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Realistic Indian Names
FIRST_NAMES = ["Aarav", "Advait", "Arjun", "Ananya", "Ishani", "Kabir", "Meera", "Neha", "Rohan", "Saanvi", "Vivaan", "Zoya", "Aditya", "Diya", "Aryan", "Isha", "Krishna", "Myra", "Pranav", "Riya", "Siddharth", "Tara", "Vihaan", "Aavya", "Akash", "Bhavya", "Chaitanya", "Deepak", "Esha", "Gautam"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Kapoor", "Singh", "Jain", "Mehta", "Patel", "Reddy", "Nair", "Iyer", "Chaudhary", "Deshmukh", "Kulkarni", "Mishra", "Pandey", "Yadav", "Rao", "Bose"]

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

# 1. Generate Faculty
faculty_list = []
faculty_id_counter = 1
faculty_by_dept = {dept: [] for dept in DEPARTMENTS}

for dept in DEPARTMENTS:
    for i in range(FACULTY_PER_DEPT):
        title = "Dr." if random.random() > 0.5 else "Asst. Prof."
        name = f"{title} {generate_name()}"
        email = f"{name.lower().replace(' ', '.').replace('..', '.')}@university.edu"
        contact = f"{random.randint(7000000000, 9999999999)}"
        faculty_info = {
            'faculty_id': faculty_id_counter,
            'faculty_name': name,
            'email': email,
            'contact_no': contact,
            'department': dept
        }
        faculty_list.append(faculty_info)
        faculty_by_dept[dept].append(name)
        faculty_id_counter += 1

with open(os.path.join(OUTPUT_DIR, 'faculty.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['faculty_id', 'faculty_name', 'email', 'contact_no', 'department'])
    writer.writeheader()
    writer.writerows(faculty_list)

# 2. Generate Subjects
subjects_list = []
subject_id_counter = 1
subjects_by_sem = {} # (dept, sem) -> [subject_info]

for dept, sems in DEPARTMENTS.items():
    for sem in sems:
        subjects_by_sem[(dept, sem)] = []
        for i in range(SUBJECTS_PER_SEM):
            subject_name = f"{dept} Sem {sem} - Subject {i+1}"
            assigned_faculty = random.choice(faculty_by_dept[dept])
            subject_info = {
                'subject_id': subject_id_counter,
                'subject_name': subject_name,
                'department': dept,
                'semester': sem,
                'faculty_name': assigned_faculty
            }
            subjects_list.append(subject_info)
            subjects_by_sem[(dept, sem)].append(subject_info)
            subject_id_counter += 1

with open(os.path.join(OUTPUT_DIR, 'subjects.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['subject_id', 'subject_name', 'department', 'semester', 'faculty_name'])
    writer.writeheader()
    writer.writerows(subjects_list)

# 3. Generate Students
students_list = []
enrollment_counter = 20240001
students_by_sem = {} # (dept, sem) -> [student_info]

for dept, sems in DEPARTMENTS.items():
    for sem in sems:
        students_by_sem[(dept, sem)] = []
        for i in range(STUDENTS_PER_SEM):
            name = generate_name()
            enroll_no = f"EN{enrollment_counter}"
            # Use enrollment counter to ensure email uniqueness
            email = f"{name.lower().replace(' ', '.')}.{enrollment_counter}@student.com"
            contact = f"{random.randint(6000000000, 8999999999)}"
            student_info = {
                'enrollment_no': enroll_no,
                'name': name,
                'email': email,
                'contact_no': contact,
                'department': dept,
                'semester': sem
            }
            students_list.append(student_info)
            students_by_sem[(dept, sem)].append(student_info)
            enrollment_counter += 1

with open(os.path.join(OUTPUT_DIR, 'students.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['enrollment_no', 'name', 'email', 'contact_no', 'department', 'semester'])
    writer.writeheader()
    writer.writerows(students_list)

# 4. Generate Marks & 5. Attendance
marks_list = []
attendance_list = []

date_list = []
curr_date = START_DATE
while curr_date <= END_DATE:
    if curr_date.weekday() < 5: # Monday to Friday
        date_list.append(curr_date.strftime('%Y-%m-%d'))
    curr_date += timedelta(days=1)

for (dept, sem), students in students_by_sem.items():
    subjects = subjects_by_sem[(dept, sem)]
    
    # Identify toppers and failures for this sem
    topper_indices = random.sample(range(STUDENTS_PER_SEM), random.randint(3, 5))
    fail_indices = random.sample([i for i in range(STUDENTS_PER_SEM) if i not in topper_indices], random.randint(3, 5))
    
    for idx, student in enumerate(students):
        enroll_no = student['enrollment_no']
        
        # Performance category
        if idx in topper_indices:
            category = 'topper'
            attendance_range = (80, 95)
            marks_range = (85, 95)
        elif idx in fail_indices:
            category = 'fail'
            attendance_range = (30, 55)
            marks_range = (15, 38)
        else:
            category = 'average'
            attendance_range = (60, 75)
            marks_range = (50, 75)
            
        for subject in subjects:
            # Generate Marks
            target_total = random.randint(marks_range[0], marks_range[1])
            # Split marks: Internal(30), Viva(10), External(60)
            internal = int(target_total * 0.3)
            viva = int(target_total * 0.1)
            external = target_total - internal - viva
            
            # Ensure within bounds (approximate)
            internal = min(internal, 30)
            viva = min(viva, 10)
            external = min(external, 60)
            
            marks_list.append({
                'enrollment_no': enroll_no,
                'subject_name': subject['subject_name'],
                'faculty_name': subject['faculty_name'],
                'internal_marks': internal,
                'viva_marks': viva,
                'external_marks': external,
                'semester': sem
            })
            
            # Generate Attendance
            att_pct = random.randint(attendance_range[0], attendance_range[1])
            for d in date_list:
                status = 'Present' if random.randint(1, 100) <= att_pct else 'Absent'
                attendance_list.append({
                    'enrollment_no': enroll_no,
                    'subject_id': subject['subject_id'],
                    'date': d,
                    'status': status
                })

with open(os.path.join(OUTPUT_DIR, 'marks.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['enrollment_no', 'subject_name', 'faculty_name', 'internal_marks', 'viva_marks', 'external_marks', 'semester'])
    writer.writeheader()
    writer.writerows(marks_list)

with open(os.path.join(OUTPUT_DIR, 'attendance.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['enrollment_no', 'subject_id', 'date', 'status'])
    writer.writeheader()
    writer.writerows(attendance_list)

print(f"Dataset generated successfully in '{OUTPUT_DIR}' folder.")
