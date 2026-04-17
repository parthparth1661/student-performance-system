import os
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

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(student_bp)

@app.route('/')
def home():
    """System entry point: Redirects to administrative nexus"""
    return redirect('/admin/login')

# --- 🔐 PASSWORD RECOVERY UNIT (NON-OTP VERSION) ---

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Simple identity verification for system administrator
        if email != app.config['EMAIL_ADDRESS']:
            flash("Authorization Denied: Access reserved for System Administrator.", "danger")
            return render_template('forgot_password.html')

        # Directly authorize session for reset protocol
        session['reset_email'] = email
        session['reset_authorized'] = True
        flash("Identity Verified. You may now update your administrative credentials.", "success")
        return redirect(url_for('reset_password'))
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if not session.get('reset_authorized'): 
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_pw = request.form.get('password')
        if not new_pw or len(new_pw) < 4:
            flash("Credential Requirements: Minimum 4 characters.", "warning")
            return render_template('reset_password.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE admin SET password=%s WHERE email=%s", 
                           (generate_password_hash(new_pw), session['reset_email']))
            conn.commit()
            session.clear()
            flash("Security Credentials updated successfully. Please re-authenticate.", "success")
            return redirect('/admin/login')
        except Exception as e:
            flash(f"System Error: Could not update credentials ({e})", "danger")
        finally:
            conn.close()
            
    return render_template('reset_password.html')

if __name__ == '__main__':
    # Initialize vital asset architecture
    for dir_name in ['static/charts', 'static/uploads']:
        if not os.path.exists(dir_name): os.makedirs(dir_name)
    app.run(debug=True)
