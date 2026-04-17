import os
import random
from flask import Flask, redirect, url_for, session, request, render_template, flash, jsonify
from werkzeug.security import generate_password_hash
from admin_routes import admin_bp
from student_routes import student_bp
from db import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = "SPDA_SECURE_ADMIN_KEY_2024"
app.permanent_session_lifetime = 1800  # 30 mins
app.config['MYSQL_DB'] = 'SPDA'

# 📧 EMAIL CONFIGURATION (GMAIL SMTP)
app.config['EMAIL_ADDRESS'] = "khevnamodi2@gmail.com"
app.config['EMAIL_PASSWORD'] = "scaaqwingmrdomvs" # 16-digit Gmail App Password

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(student_bp)

@app.route('/')
def home():
    """System entry point: Redirects to administrative nexus"""
    return redirect('/admin/login')

# --- 🔐 PASSWORD RECOVERY UNIT ---

def send_otp(email, otp):
    """Dispatches secure verification tokens via SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(f"Your Institutional Access Verification Token (OTP) is: {otp}")
    msg['Subject'] = "Protocol: OTP Verification"
    msg['From'] = app.config['EMAIL_ADDRESS']
    msg['To'] = email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(app.config['EMAIL_ADDRESS'], app.config['EMAIL_PASSWORD'])
        server.sendmail(app.config['EMAIL_ADDRESS'], email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Critical Error: {e}")
        return False

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        if email != app.config['EMAIL_ADDRESS']:
            flash("Authorization Denied: Access reserved for System Administrator.", "danger")
            return render_template('forgot_password.html')

        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['reset_email'] = email

        if send_otp(email, otp):
            flash("Security Token dispatched to recovery email.", "success")
            return redirect(url_for('verify_otp'))
        flash("Gateway Timeout: SMTP Dispatch failure.", "danger")
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if not session.get('reset_email'): return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        if request.form.get('otp') == session.get('otp'):
            session['otp_verified'] = True
            return redirect(url_for('reset_password'))
        flash("Invalid or expired verification credentials.", "danger")
    return render_template('verify_otp.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('otp_verified'): return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        new_pw = request.form.get('password')
        if not new_pw or len(new_pw) < 4:
            flash("Credential Requirements: Minimum 4 characters.", "warning")
            return render_template('reset_password.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admin SET password=%s WHERE email=%s", (generate_password_hash(new_pw), session['reset_email']))
        conn.commit()
        conn.close()
        session.clear()
        flash("Security Credentials updated. Please re-authenticate.", "success")
        return redirect('/admin/login')
    return render_template('reset_password.html')

if __name__ == '__main__':
    # Initialize vital asset architecture
    for dir_name in ['static/charts', 'static/uploads']:
        if not os.path.exists(dir_name): os.makedirs(dir_name)
    app.run(debug=True)
