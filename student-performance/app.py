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
    except Exception as e:
        print(f"Upload error: {e}")

    return redirect(url_for('admin.view_students'))


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






