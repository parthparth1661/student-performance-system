from flask import Flask, redirect, url_for, session
from admin_routes import admin_bp
from student_routes import student_bp
from db import init_db
import os

app = Flask(__name__)
# 1. Force Logout on App Start: Random key invalidates old sessions on restart
app.secret_key = os.urandom(24)
app.config['MYSQL_DB'] = 'SPDA' # Set Default Database 🔥

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(student_bp)

@app.route('/')
def index():
    from flask import render_template
    return render_template('landing_page.html')

@app.route('/profile')
def profile():
    from flask import render_template, session, redirect, url_for
    if not session.get('admin_email'):
        return redirect(url_for('admin.login'))
    
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admin WHERE email = %s", (session.get('admin_email'),))
    admin_data = cursor.fetchone()
    conn.close()
    
    return render_template('profile.html', admin=admin_data)

@app.route('/upload_students_csv', methods=['POST'])
def upload_students_csv():
    from flask import request, redirect, url_for, session
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))

    file = request.files['file']
    import csv
    from db import get_db_connection
    from werkzeug.security import generate_password_hash

    try:
        data = csv.DictReader(file.read().decode('utf-8').splitlines())
        conn = get_db_connection()
        cursor = conn.cursor()

        for row in data:
            name = row.get('name')
            enrollment_no = row.get('enrollment_no')
            department = row.get('department')
            semester = row.get('semester')

            if not name or not enrollment_no:
                continue

            # 🛡️ Duplicate check (Safe & Simple)
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no=%s", (enrollment_no,))
            if cursor.fetchone():
                continue

            # Default credentials for Bulk Upload
            email = f"{enrollment_no}@spda.com"
            pw_hash = generate_password_hash(enrollment_no + "@123")

            # insert into DB
            cursor.execute(
                "INSERT INTO students (name, enrollment_no, email, department, semester, password_hash) VALUES (%s,%s,%s,%s,%s,%s)",
                (name, enrollment_no, email, department, semester, pw_hash)
            )
            
            # 📝 LOG ACTION (Minimal)
            cursor.execute("INSERT INTO activity_logs (action) VALUES (%s)", (f"Bulk Upload: Student {enrollment_no}",))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Upload error: {e}")

    return redirect(url_for('admin.view_students'))

@app.route('/upload_marks_csv', methods=['POST'])
def upload_marks_csv():
    from flask import request, redirect, url_for, session
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))

    file = request.files['file']
    import csv
    from db import get_db_connection

    try:
        data = csv.DictReader(file.read().decode('utf-8').splitlines())
        conn = get_db_connection()
        cursor = conn.cursor()

        for row in data:
            enrollment_no = row.get('enrollment_no')
            subject = row.get('subject')
            marks_obtained = row.get('marks')

            if not enrollment_no or not subject or not marks_obtained:
                continue

            # 🛡️ 1. Validate Subject Existence
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_name=%s", (subject,))
            sub_res = cursor.fetchone()
            if not sub_res: 
                continue # Skip if subject not found
            subject_id = sub_res[0]

            # 🛡️ 2. Validate Student Existence
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no=%s", (enrollment_no,))
            if not cursor.fetchone():
                continue # Skip if student not found

            # 🛡️ 3. Safe Insert with logical defaults
            try:
                marks_val = float(marks_obtained)
                status = 'PASS' if marks_val >= 40 else 'FAIL'
                cursor.execute(
                    "INSERT INTO marks (enrollment_no, subject_id, marks_obtained, exam_type, status) VALUES (%s,%s,%s,%s,%s)",
                    (enrollment_no, subject_id, marks_val, 'Final', status)
                )
                
                # 📝 LOG ACTION
                cursor.execute("INSERT INTO activity_logs (action) VALUES (%s)", (f"Bulk Upload: Marks for {enrollment_no}",))
            except ValueError:
                continue

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Marks Upload Error: {e}")

    return redirect(url_for('admin.view_marks'))

@app.route('/upload_subjects_csv', methods=['POST'])
def upload_subjects_csv():
    from flask import request, redirect, url_for, session
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))

    file = request.files['file']
    import csv
    from db import get_db_connection

    try:
        data = csv.DictReader(file.read().decode('utf-8').splitlines())
        conn = get_db_connection()
        cursor = conn.cursor()

        for row in data:
            name = row.get('subject_name')
            dept = row.get('department')
            sem = row.get('semester')

            if not name or not dept or not sem:
                continue

            # 🛡️ Duplicate check (Optional but safe)
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_name=%s AND department=%s AND semester=%s", (name, dept, sem))
            if cursor.fetchone():
                continue

            # insert into DB
            cursor.execute(
                "INSERT INTO subjects (subject_name, department, semester) VALUES (%s,%s,%s)",
                (name, dept, sem)
            )
            
            # 📝 LOG ACTION
            cursor.execute("INSERT INTO activity_logs (action) VALUES (%s)", (f"Bulk Upload: Subject {name}",))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Subjects Upload error: {e}")

    return redirect(url_for('admin.view_subjects'))

@app.route('/upload_attendance_csv', methods=['POST'])
def upload_attendance_csv():
    from flask import request, redirect, url_for, session
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))

    file = request.files['file']
    import csv
    from db import get_db_connection

    try:
        data = csv.DictReader(file.read().decode('utf-8').splitlines())
        conn = get_db_connection()
        cursor = conn.cursor()

        for row in data:
            en_no = row.get('enrollment_no')
            subject_name = row.get('subject')
            att_date = row.get('date')
            status = row.get('status')

            if not all([en_no, subject_name, att_date, status]):
                continue

            # 🛡️ 1. Validate Subject
            cursor.execute("SELECT subject_id FROM subjects WHERE subject_name=%s", (subject_name,))
            res = cursor.fetchone()
            if not res: continue
            sub_id = res[0]

            # 🛡️ 2. Status check
            if status not in ['Present', 'Absent']:
                continue

            # 🛡️ 3. Duplicate check (prevent double logging for same student+subject+day)
            cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no=%s AND subject_id=%s AND date=%s", (en_no, sub_id, att_date))
            if cursor.fetchone():
                continue

            # insert into DB
            cursor.execute(
                "INSERT INTO attendance (enrollment_no, subject_id, date, status) VALUES (%s,%s,%s,%s)",
                (en_no, sub_id, att_date, status)
            )
            
            # 📝 LOG ACTION
            cursor.execute("INSERT INTO activity_logs (action) VALUES (%s)", (f"Bulk Upload: Attendance for {en_no}",))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Attendance Upload error: {e}")

    return redirect(url_for('admin.view_attendance'))

@app.route('/logs')
def logs():
    from flask import session, redirect, url_for, render_template
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM activity_logs ORDER BY timestamp DESC")
    logs_data = cursor.fetchall()
    conn.close()
    return render_template('admin/logs.html', logs=logs_data)


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






