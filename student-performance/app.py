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



@app.route('/export_students_csv')
def export_students_csv():
    from flask import session, redirect, url_for, Response, request
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    import csv
    import io
    from datetime import datetime
    from db import get_db_connection
    from analysis import get_performance_overview

    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'attendance': request.args.get('attendance'),
        'subject': request.args.get('subject')
    }

    data, _ = get_performance_overview(filters, limit=1000)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conn.commit()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Enrollment No', 'Name', 'Department', 'Semester', 'Subject', 'Marks Obtained', 'Attendance %', 'Status'])
    
    for row in data:
        status = 'PASS' if row['marks_obtained'] >= 40 else 'FAIL'
        writer.writerow([
            row['enrollment_no'], 
            row['name'], 
            row['department'], 
            row['semester'], 
            row['subject_name'], 
            round(row['marks_obtained'], 2), 
            round(row['attendance_percentage'], 2),
            status
        ])

    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename=SPDA_Report_{datetime.now().strftime('%Y%m%d')}.csv"})

@app.route('/export_students_pdf')
def export_students_pdf():
    from flask import session, redirect, url_for, send_file, request
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login'))
        
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    import os
    from datetime import datetime
    from db import get_db_connection
    from analysis import get_dashboard_stats, get_performance_overview, generate_dashboard_charts

    filters = {
        'department': request.args.get('department'),
        'semester': request.args.get('semester'),
        'search': request.args.get('search'),
        'attendance': request.args.get('attendance'),
        'subject': request.args.get('subject')
    }

    # Gather Data
    stats = get_dashboard_stats(filters)
    data, _ = get_performance_overview(filters, limit=50) # Limit for PDF readability
    generate_dashboard_charts(filters) # Refresh chart images with filters

    conn = get_db_connection()
    cursor = conn.cursor()
    
    conn.commit()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # 📄 1. HEADER
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph("System: SPDA Admin Panel", header_style))
    elements.append(Paragraph(f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", header_style))
    elements.append(Spacer(1, 0.2*inch))
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=22, spaceAfter=10, textColor=colors.HexColor('#1e293b'))
    elements.append(Paragraph("Student Performance Report", title_style))
    
    filter_text = f"Filters: Dept={filters['department'] or 'All'} | Sem={filters['semester'] or 'All'} | Sub={filters['subject'] or 'All'}"
    elements.append(Paragraph(filter_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))

    # 📊 2. SUMMARY SECTION
    summary_data = [
        ['Metric', 'Value'],
        ['Total Population', str(stats['total_students'])],
        ['Institutional Avg Marks', f"{stats['avg_marks']}%"],
        ['Global Attendance Rate', f"{stats['attendance_percentage']}%"],
        ['Performance Leader', stats['top_performer']]
    ]
    summary_table = Table(summary_data, colWidths=[2.5*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))

    # 📈 3. CHARTS
    elements.append(Paragraph("Visual Performance Analytics", styles['Heading2']))
    chart_files = ['subject_avg.png', 'attendance_pie.png']
    for chart in chart_files:
        chart_path = os.path.join(os.path.dirname(__file__), 'static', 'charts', chart)
        if os.path.exists(chart_path):
            img = Image(chart_path, width=4.5*inch, height=2.8*inch)
            elements.append(img)
            elements.append(Spacer(1, 0.2*inch))
    
    elements.append(PageBreak())

    # 📋 4. MAIN DATA TABLE
    elements.append(Paragraph("Detailed Performance Matrix", styles['Heading2']))
    table_headers = ['Enrollment', 'Student Name', 'Subject', 'Marks', 'Attn %', 'Status']
    table_rows = [table_headers]
    
    alerts_low_marks = []
    alerts_low_attn = []

    for row in data:
        status = 'PASS' if row['marks_obtained'] >= 40 else 'FAIL'
        table_rows.append([
            row['enrollment_no'],
            row['name'][:15] + ('..' if len(row['name']) > 15 else ''),
            row['subject_name'][:12],
            f"{round(row['marks_obtained'],1)}",
            f"{round(row['attendance_percentage'],1)}%",
            status
        ])
        
        if row['marks_obtained'] < 40: alerts_low_marks.append(row['name'])
        if row['attendance_percentage'] < 75: alerts_low_attn.append(row['name'])

    perf_table = Table(table_rows, colWidths=[1*inch, 1.8*inch, 1.5*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    perf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
    ]))
    elements.append(perf_table)
    elements.append(Spacer(1, 0.4*inch))

    # ⚠️ 5. ALERT SECTION
    if alerts_low_marks or alerts_low_attn:
        elements.append(Paragraph("Critical Performance Alerts", styles['Heading2']))
        if alerts_low_marks:
            elements.append(Paragraph(f"⚠️ Students at Risk (Marks < 40): {', '.join(list(set(alerts_low_marks))[:5])}", styles['Normal']))
        if alerts_low_attn:
            elements.append(Paragraph(f"📉 Attendance Defaulters (< 75%): {', '.join(list(set(alerts_low_attn))[:5])}", styles['Normal']))
        elements.append(Spacer(1, 0.4*inch))

    # 🧱 6. FOOTER
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
    elements.append(Spacer(1, 1*inch))
    elements.append(Paragraph("Generated by SPDA Admin Panel - Institutional Performance Division", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"SPDA_Executive_Report_{datetime.now().strftime('%M%S')}.pdf", mimetype='application/pdf')


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






