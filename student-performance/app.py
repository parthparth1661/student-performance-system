from flask import Flask, redirect, url_for, session, request
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

@app.before_request
def clear_session_on_start():
    # Force session clearance only when accessing the root 'home' entry point
    if request.endpoint == 'home':
        session.clear()

@app.route('/')
def home():
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

# Redundant Upload and Export routes moved to admin_routes.py for better modularization

# PDF Export functionality is managed within the admin blueprint (admin_routes.py)


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






