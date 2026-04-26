import csv
import os
import random
from datetime import datetime, timedelta

# Configuration
DEPARTMENTS = {
    'BCA': range(1, 7),
    'MCA': range(1, 5)
}

STUDENTS_PER_SEM = 30
SUBJECTS_PER_SEM = 4
START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 2, 28)

OUTPUT_DIR = 'dataset_csv'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Realistic Indian Names
FIRST_NAMES = ["Aarav", "Advait", "Arjun", "Ananya", "Ishani", "Kabir", "Meera", "Neha", "Rohan", "Saanvi", "Vivaan", "Zoya", "Aditya", "Diya", "Aryan", "Isha", "Krishna", "Myra", "Pranav", "Riya", "Siddharth", "Tara", "Vihaan", "Aavya", "Akash", "Bhavya", "Chaitanya", "Deepak", "Esha", "Gautam", "Parth", "Khevna"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Kapoor", "Singh", "Jain", "Mehta", "Patel", "Reddy", "Nair", "Iyer", "Chaudhary", "Deshmukh", "Kulkarni", "Mishra", "Pandey", "Yadav", "Rao", "Bose", "Prajapati", "Modi"]

FACULTY_FIRST = ["Rajesh", "Suresh", "Ramesh", "Priya", "Anjali", "Vikram", "Amit", "Kavita", "Sunil", "Ravi", "Sanjay", "Vinod", "Geeta", "Kiran"]
FACULTY_LAST = ["Sharma", "Mehta", "Patel", "Joshi", "Iyer", "Rao", "Nair", "Gupta", "Kumar", "Singh", "Desai"]

REALISTIC_SUBJECTS = [
    "Python Programming", "Java Programming", "C Programming", "Data Structures",
    "Database Management System", "Operating System", "Computer Networks", "Software Engineering",
    "Web Technologies", "Machine Learning", "Artificial Intelligence", "Cloud Computing",
    "Cyber Security", "Data Mining", "Internet of Things", "Mobile Application Development",
    "Discrete Mathematics", "Digital Logic", "Computer Architecture", "Theory of Computation",
    "Design and Analysis of Algorithms", "Computer Graphics", "Compiler Design", "Microprocessors",
    "Data Science", "Big Data Analytics", "Deep Learning", "Natural Language Processing",
    "Information Security", "Software Testing", "Object Oriented Analysis and Design", "Advanced Java",
    "Advanced Database", "Network Security", "Cryptography", "Distributed Systems",
    "E-Commerce", "Management Information Systems", "Computer Vision", "Human Computer Interaction",
    "Blockchain Technology", "Bioinformatics", "Quantum Computing", "Embedded Systems"
]

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_faculty_name():
    title = random.choice(["Dr.", "Prof."])
    return f"{title} {random.choice(FACULTY_FIRST)} {random.choice(FACULTY_LAST)}"

# 1. Generate Faculty
faculty_list = []
faculty_by_dept = {dept: [] for dept in DEPARTMENTS}
faculty_id_counter = 1

for dept in DEPARTMENTS:
    num_faculty = random.randint(3, 5)
    for _ in range(num_faculty):
        name = generate_faculty_name()
        email = f"{name.lower().replace(' ', '.').replace('..', '.')}.{faculty_id_counter}@university.edu"
        contact = f"{random.randint(7000000000, 9999999999)}"
        faculty_info = {
            'faculty_id': faculty_id_counter,
            'faculty_name': name,
            'email': email,
            'department': dept,
            'contact_no': contact
        }
        faculty_list.append(faculty_info)
        faculty_by_dept[dept].append(name)
        faculty_id_counter += 1

with open(os.path.join(OUTPUT_DIR, 'faculty.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['faculty_id', 'faculty_name', 'email', 'department', 'contact_no'])
    writer.writeheader()
    writer.writerows(faculty_list)

# 2. Generate Subjects
subjects_list = []
subject_id_counter = 1
subjects_by_sem = {} # (dept, sem) -> [subject_info]

# Shuffle subjects to pick from them
random.shuffle(REALISTIC_SUBJECTS)
subject_pool_index = 0

for dept, sems in DEPARTMENTS.items():
    for sem in sems:
        subjects_by_sem[(dept, sem)] = []
        for i in range(SUBJECTS_PER_SEM):
            subject_name = REALISTIC_SUBJECTS[subject_pool_index % len(REALISTIC_SUBJECTS)]
            subject_pool_index += 1
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
students_by_sem = {} # (dept, sem) -> [student_info]

for dept, sems in DEPARTMENTS.items():
    for sem in sems:
        students_by_sem[(dept, sem)] = []
        for i in range(1, STUDENTS_PER_SEM + 1):
            name = generate_name()
            # Format: BCA101, MCA215, etc.
            enroll_no = f"{dept}{sem}{i:02d}"
            email = f"{name.lower().replace(' ', '.')}.{enroll_no}@student.com"
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
    
    # Identify toppers, fail, and average students for accurate representation
    student_indices = list(range(STUDENTS_PER_SEM))
    random.shuffle(student_indices)
    topper_indices = student_indices[:5]  # ~5 toppers
    fail_indices = student_indices[5:10]  # ~5 fails
    avg_indices = student_indices[10:]    # ~20 average
    
    for idx, student in enumerate(students):
        enroll_no = student['enrollment_no']
        
        # Performance category mappings
        if idx in topper_indices:
            attendance_range = (80, 95)
            marks_range = (80, 95)
        elif idx in fail_indices:
            attendance_range = (30, 50)
            marks_range = (20, 40)
        else:
            attendance_range = (60, 75)
            marks_range = (50, 75)
            
        for subject in subjects:
            # Generate Marks
            target_total = random.randint(marks_range[0], marks_range[1])
            
            # Smart split: internal(30), viva(10), external(60)
            internal_target = int(target_total * 0.3)
            viva_target = int(target_total * 0.1)
            
            internal = min(internal_target, 30)
            viva = min(viva_target, 10)
            external = min(target_total - internal - viva, 60)
            
            # Recalculate if external was capped at 60 but target is higher
            remainder = target_total - (internal + viva + external)
            if remainder > 0:
                add_int = min(remainder, 30 - internal)
                internal += add_int
                remainder -= add_int
                add_viv = min(remainder, 10 - viva)
                viva += add_viv
            
            marks_list.append({
                'enrollment_no': enroll_no,
                'subject_name': subject['subject_name'],
                'internal_marks': internal,
                'viva_marks': viva,
                'external_marks': external
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
    writer = csv.DictWriter(f, fieldnames=['enrollment_no', 'subject_name', 'internal_marks', 'viva_marks', 'external_marks'])
    writer.writeheader()
    writer.writerows(marks_list)

with open(os.path.join(OUTPUT_DIR, 'attendance.csv'), 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['enrollment_no', 'subject_id', 'date', 'status'])
    writer.writeheader()
    writer.writerows(attendance_list)

print(f"Dataset successfully generated with STRICT relational integrity in '{OUTPUT_DIR}' folder.")
