import csv
import random

# Configuration
DEPARTMENTS = {
    'BCA': ['Python Programming', 'Java Programming', 'DBMS', 'Data Structures', 'Operating Systems', 'Web Technology'],
    'MCA': ['Advanced Python', 'Java', 'DBMS', 'DSA', 'Computer Networks', 'Software Engineering'],
    'B.TECH': ['Engineering Mathematics', 'Data Structures', 'DBMS', 'Operating Systems', 'Computer Networks', 'Software Engineering'],
    'M.TECH': ['Advanced Algorithms', 'Machine Learning', 'Cloud Computing', 'Distributed Systems', 'Data Mining', 'Research Methodology'],
    'MBA': ['Marketing Management', 'Financial Management', 'Human Resource Management', 'Operations Management', 'Business Analytics', 'Strategic Management']
}

EXAM_DATES = {
    'Internal': '2026-02-05',
    'Practical': '2026-02-12',
    'External': '2026-03-10'
}

TOTAL_STUDENTS_PER_DEPT = 20
SEMESTER = 1

def generate_realistic_marks():
    rand = random.random()
    if rand < 0.05: # 5% fail marks
        return random.randint(15, 34)
    elif rand < 0.15: # 10% just pass
        return random.randint(35, 45)
    elif rand < 0.70: # 55% average (45-80)
        return random.randint(46, 80)
    elif rand < 0.95: # 25% good (81-90)
        return random.randint(81, 90)
    else: # 5% toppers
        return random.randint(91, 100)

first_names = ["Rahul", "Anjali", "Sneha", "Amit", "Priya", "Vikram", "Neha", "Arjun", "Karan", "Simran", "Ishaan", "Riya", "Aditya", "Sanya", "Manish", "Pooja", "Siddharth", "Tanya", "Vivek", "Amrita"]
last_names = ["Sharma", "Verma", "Gupta", "Malhotra", "Kapoor", "Joshi", "Singhania", "Chopra", "Mehta", "Bose", "Khanna", "Agarwal", "Reddy", "Patel", "Nair", "Saxena", "Trivedi", "Pandey", "Iyer", "Yadav"]

dataset = []

roll_counter = 1001

for dept, subjects in DEPARTMENTS.items():
    for i in range(TOTAL_STUDENTS_PER_DEPT):
        first = random.choice(first_names)
        last = random.choice(last_names)
        name = f"{first} {last}"
        roll_no = f"{dept[:1]}{roll_counter}"
        # Small tweak for B.TECH/M.TECH shorthand
        if dept == 'B.TECH': roll_no = f"BT{roll_counter}"
        elif dept == 'M.TECH': roll_no = f"MT{roll_counter}"
        
        email = f"{first.lower()}.{last.lower()}.{roll_no.lower()}@example.com"
        roll_counter += 1
        
        # Some students consistently good, some struggle
        student_base_offset = random.randint(-15, 15)
        
        for subject in subjects:
            exam_types = ['Internal', 'External', 'Practical']
            if dept == 'MBA':
                exam_types = ['Internal', 'External']
            
            for etype in exam_types:
                marks = generate_realistic_marks()
                # Apply student offset but clamp to 0-100
                marks = max(0, min(100, marks + student_base_offset))
                
                dataset.append({
                    'roll_no': roll_no,
                    'name': name,
                    'email': email,
                    'department': dept,
                    'semester': SEMESTER,
                    'subject': subject,
                    'marks': marks,
                    'exam_type': etype,
                    'exam_date': EXAM_DATES[etype]
                })

with open('test_data_100_students.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['roll_no', 'name', 'email', 'department', 'semester', 'subject', 'marks', 'exam_type', 'exam_date'])
    writer.writeheader()
    writer.writerows(dataset)

print(f"Generated {len(dataset)} rows of test data.")
