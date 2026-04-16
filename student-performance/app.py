from flask import Flask, redirect, url_for, session
from admin_routes import admin_bp
from student_routes import student_bp
from db import init_db
import os
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
# 1. Force Logout on App Start: Random key invalidates old sessions on restart
app.secret_key = "SPDA_SECURE_ADMIN_KEY_2024"
app.permanent_session_lifetime = 1800 # 30 mins
app.config['MYSQL_DB'] = 'SPDA' 

# 📧 EMAIL CONFIGURATION (GMAIL SMTP)
app.config['EMAIL_ADDRESS'] = "khevnamodi2@gmail.com"
app.config['EMAIL_PASSWORD'] = "your_16_digit_app_password" # ⚠️ MUST USE 16-DIGIT GMAIL APP PASSWORD

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(student_bp)

@app.route('/')
def home():
    if session.get('admin_logged_in'):
        return redirect('/admin/dashboard')
    return redirect('/admin/login')

def send_otp(email, otp):
    import smtplib
    from email.mime.text import MIMEText

    EMAIL = "khevnamodi2@gmail.com"
    PASSWORD = "scaaqwingmrdomvs"  # 16-digit app password (NO spaces)

    msg = MIMEText(f"Your OTP is: {otp}")
    msg['Subject'] = "OTP Verification"
    msg['From'] = EMAIL
    msg['To'] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, email, msg.as_string())
        server.quit()
        print("OTP SENT SUCCESS")
        return True

    except Exception as e:
        print("REAL ERROR:", str(e))   # 🔥 IMPORTANT
        return False

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    from flask import request, render_template, flash, redirect, url_for
    if request.method == 'POST':
        email = request.form.get('email')
        
        if email != "khevnamodi2@gmail.com":
            flash("Authorization Denied: Invalid Administrator Email.", "danger")
            return render_template('forgot_password.html')

        import random
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['reset_email'] = email

        if send_otp(email, otp):
            flash("Secure OTP sent to khevnamodi2@gmail.com", "success")
            return redirect(url_for('verify_otp'))
        else:
            flash("Communication Failure: Could not dispatch OTP.", "danger")
            return render_template('forgot_password.html')

    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    from flask import request, render_template, flash, redirect, url_for
    if not session.get('reset_email') or not session.get('otp'):
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        if user_otp == session.get('otp'):
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid or expired verification code.", "danger")
            return render_template('verify_otp.html')

    return render_template('verify_otp.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    from flask import request, render_template, flash, redirect, url_for
    from werkzeug.security import generate_password_hash
    from db import get_db_connection

    if not session.get('otp_verified'):
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        if not new_password or len(new_password) < 4:
            flash("Password must be at least 4 characters.", "danger")
            return render_template('reset_password.html')

        hashed = generate_password_hash(new_password)
        email = session.get('reset_email')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE admin SET password=%s WHERE email=%s", (hashed, email))
            conn.commit()
            session.clear()
            flash("Password updated successfully. Please login.", "success")
            return redirect('/admin/login')
        except Exception as e:
            flash(f"Database error: {e}", "danger")
        finally:
            conn.close()

    return render_template('reset_password.html')

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
            


        conn.commit()
        conn.close()
        from flask import flash
        flash("Student CSV uploaded successfully!", "success")
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
            en_no = row.get('enrollment_no')
            subject = row.get('subject')
            dept = row.get('department')
            sem = row.get('semester')
            
            # 🧱 STEP 2 — CALCULATE TOTAL (MAIN LOGIC)
            # Handle different CSV headers (marks vs components)
            try:
                internal = float(row.get('internal_marks') or 0)
                viva = float(row.get('viva_marks') or 0)
                external = float(row.get('external_marks') or 0)
            except ValueError:
                print(f"Skipping row for {en_no}: Invalid numeric marks")
                continue
                
            total_marks = internal + viva + external

            # 🧱 STEP 5 — VALIDATION (IMPORTANT)
            if not (0 <= internal <= 30 and 0 <= viva <= 10 and 0 <= external <= 60):
                print(f"Skipping row for {en_no}: Component range violation")
                continue

            if total_marks > 100:
                print("Invalid marks") # Per Step 5 requirements
                continue

            if not en_no or not subject or not dept or not sem:
                continue

            # 🛡️ 1. Find EXACT Subject ID
            cursor.execute("""
                SELECT subject_id FROM subjects 
                WHERE subject_name=%s AND department=%s AND semester=%s
            """, (subject, dept, sem))
            sub_res = cursor.fetchone()
            if not sub_res: 
                continue 
            sub_id = sub_res[0]

            # 🛡️ 2. Validate Student
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no=%s", (en_no,))
            if not cursor.fetchone():
                continue

            # 🛡️ 3. Duplicate Prevention (enrollment_no + subject_id)
            cursor.execute("""
                SELECT id FROM marks 
                WHERE enrollment_no=%s AND subject_id=%s
            """, (en_no, sub_id))
            if cursor.fetchone():
                continue

            # 🛡️ 4. Safe Insert (Mapping components to DB)
            cursor.execute("""
                INSERT INTO marks (enrollment_no, subject_id, internal_marks, viva_marks, external_marks, total_marks) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (en_no, sub_id, internal, viva, external, total_marks))
            
            

        conn.commit()
        conn.close()
        from flask import flash
        flash("Marks CSV uploaded successfully!", "success")
    except Exception as e:
        print(f"Marks Upload Error: {e}")

    return redirect(url_for('admin.view_marks'))

@app.route('/clear_students')
def clear_students():
    from flask import session, redirect, url_for
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Order is critical due to foreign keys
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM marks")
        cursor.execute("DELETE FROM students")
        conn.commit()
    except Exception as e:
        print(f"Clear Students Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('admin.view_students'))

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
            
            

        conn.commit()
        conn.close()
        from flask import flash
        flash("Subjects CSV uploaded successfully!", "success")
    except Exception as e:
        print(f"Subjects Upload error: {e}")

    return redirect(url_for('admin.view_subjects'))

@app.route('/clear_marks')
def clear_marks():
    from flask import session, redirect, url_for
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM marks")
        conn.commit()
    except Exception as e:
        print(f"Clear Marks Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('admin.view_marks'))

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

        # Process data
        for row in data:
            try:
                # 🧱 STEP 1 — PRINT FULL CSV ROW
                print("ROW DATA:", row)

                # 🧱 STEP 2 — CLEAN INPUT DATA
                enrollment_no = row.get('enrollment_no', '').strip()
                subject = row.get('subject', '').strip()
                department = row.get('department', '').strip()
                semester = int(row.get('semester', 1)) 
                date_val = row.get('date', '').strip()
                # Status formatting: capitalize to ensure "Present" / "Absent" format
                status = row.get('status', '').strip().capitalize()

                print(f"CLEANED: {enrollment_no}, {subject}, {department}, {semester}, {date_val}, {status}")

                if not all([enrollment_no, subject, department, semester, date_val, status]):
                    continue

                # 🧱 STEP 3 — DEBUG SUBJECT MATCH (TRIM in SQL 🔥)
                cursor.execute("""
                    SELECT subject_id FROM subjects
                    WHERE TRIM(subject_name)=%s AND TRIM(department)=%s AND semester=%s
                """, (subject, department, semester))

                subject_row = cursor.fetchone()
                print("SUBJECT RESULT:", subject_row)

                if not subject_row:
                    print(f"❌ SUBJECT NOT FOUND: {subject}, {department}, {semester}")
                    continue
                subject_id = subject_row[0]

                # 🧱 STEP 4 — CHECK STUDENT EXISTS
                cursor.execute("SELECT * FROM students WHERE enrollment_no=%s", (enrollment_no,))
                student = cursor.fetchone()
                if not student:
                    print(f"❌ STUDENT NOT FOUND: {enrollment_no}")
                    continue

                # 🧱 STEP 5 — VALIDATE DATA
                if status not in ["Present", "Absent"]:
                    print(f"❌ INVALID STATUS: {status}")
                    continue

                # 🛡️ Duplicate check
                cursor.execute("SELECT attendance_id FROM attendance WHERE enrollment_no=%s AND subject_id=%s AND date=%s", 
                               (enrollment_no, subject_id, date_val))
                if cursor.fetchone():
                    continue

                # 🧱 STEP 6 — INSERT DATA (CRITICAL)
                cursor.execute("""
                    INSERT INTO attendance (enrollment_no, subject_id, date, status)
                    VALUES (%s, %s, %s, %s)
                """, (enrollment_no, subject_id, date_val, status))
                
                print(f"✅ INSERTED: {enrollment_no}, {subject}, {date_val}")

            except Exception as e:
                print(f"Row error: {e}")
                continue

        conn.commit()
        conn.close()
        from flask import flash
        flash("Attendance CSV uploaded successfully!", "success")
    except Exception as e:
        print(f"Attendance Upload error: {e}")

    return redirect(url_for('admin.view_attendance'))

@app.route('/clear_attendance')
def clear_attendance():
    from flask import session, redirect, url_for
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM attendance")
        conn.commit()
    except Exception as e:
        print(f"Clear Attendance Error: {e}")
    finally:
        conn.close()
    return redirect(url_for('admin.view_attendance'))



@app.route('/export_students_pdf')
def export_students_pdf():
    from flask import session, redirect, url_for, request, render_template, make_response
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    import pdfkit
    import os
    from datetime import datetime
    from analysis import get_dashboard_stats, get_performance_overview

    # --- 🧱 STEP 1: SETUP PDFKIT ---
    # User-specified path for wkhtmltopdf
    wkhtml_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=wkhtml_path)

    # --- 🧱 STEP 2: CAPTURE FILTERS ---
    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'subject': request.args.get('subject'),
        'subject_id': request.args.get('subject_id'),
        'search': request.args.get('search'),
        'attendance': request.args.get('attendance'),
        'date': request.args.get('date')
    }

    # --- 🧱 STEP 3: GATHER DATA ---
    stats = get_dashboard_stats(filters)
    data, _ = get_performance_overview(filters, limit=500) 
    
    # --- 🧱 STEP 4: RENDER & CONVERT ---
    rendered = render_template('admin/report.html', 
                             data=data, 
                             stats=stats, 
                             filters=filters,
                             current_date=datetime.now().strftime('%d %b %Y'))

    try:
        # Generate PDF from HTML string (returns bytes)
        options = {
            'page-size': 'Letter',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None
        }
        pdf_bytes = pdfkit.from_string(rendered, False, configuration=config, options=options)

        # --- 🧱 STEP 5: SAVE ON SERVER (ARCHIVE) ---
        report_filename = f"SPDA_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        server_path = os.path.join('static', 'reports', report_filename)
        
        # Ensure directory exists (last-second check)
        if not os.path.exists('static/reports'):
            os.makedirs('static/reports')
            
        with open(server_path, 'wb') as f:
            f.write(pdf_bytes)

        # --- 🧱 STEP 6: SEND TO BROWSER (DOWNLOAD) ---
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={report_filename}'
        return response

    except Exception as e:
        # Fallback error message if wkhtmltopdf is not found or fails
        from flask import flash
        flash(f"PDF Generation Error: {str(e)}. Please ensure wkhtmltopdf is installed at {wkhtml_path}", "danger")
        return redirect(url_for('admin.dashboard'))


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






