"""
Student Performance Detection & Analysis System (SPDA)
-------------------------------------------------------
Core Application Nexus: Handles authentication, session management, 
and microservice coordination for the institutional performance engine.
"""

import os
from flask import Flask, redirect, url_for, session, request, render_template, flash, jsonify
from werkzeug.security import generate_password_hash
from admin_routes import admin_bp
from student_routes import student_bp
from db import init_db, get_db_connection

# --- 🚀 1. SYSTEM INITIALIZATION ---
app = Flask(__name__)
app.secret_key = "SPDA_SECURE_ADMIN_KEY_2024"
app.permanent_session_lifetime = 1800  # 30-minute session expiry for security
app.config['MYSQL_DB'] = 'SPDA'

# 📧 Institution Email Configuration (System Account)
app.config['EMAIL_ADDRESS'] = "khevnamodi2@gmail.com"

# Initialize persistence layer and standardized table architecture
init_db()

# --- 🛰️ 2. MICROSERVICE REGISTRATION ---
# Register administrative nexus (Departmental/Faculty management)
app.register_blueprint(admin_bp, url_prefix='/admin')
# Register student intelligence portal 
app.register_blueprint(student_bp)


# --- 🔐 3. ROUTE CONTROLLERS ---

@app.route('/')
def home():
    """
    Identity Entry Point: 
    Redirects all root traffic to the administrative login portal.
    """
    return redirect('/admin/login')


# --- 🛡️ 4. CREDENTIAL RECOVERY MODULE ---

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """
    Initiates the secure password recovery protocol for administrators.
    Performs identity verification against the institutional contact registry.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Simple identity verification for the designated System Administrator
        if email != app.config['EMAIL_ADDRESS']:
            flash("Authorization Denied: Access reserved for System Administrator.", "danger")
            return render_template('forgot_password.html')

        # Authorize the session to proceed with the secure reset protocol
        session['reset_email'] = email
        session['reset_authorized'] = True
        flash("Identity Verified. You may now update your administrative credentials.", "success")
        return redirect(url_for('reset_password'))
        
    return render_template('forgot_password.html')


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """
    Handles the final phase of the credential update protocol.
    Enforces hashing and security requirements for new passwords.
    """
    # Guard: Ensure the user has passed the identity verification gate
    if not session.get('reset_authorized'): 
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_pw = request.form.get('password')
        
        # Validation: Enforce institutional security standards
        if not new_pw or len(new_pw) < 4:
            flash("Credential Requirements: Minimum 4 characters.", "warning")
            return render_template('reset_password.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Atomic update of administrative credentials using secure hashing
            cursor.execute("UPDATE admin SET password=%s WHERE email=%s", 
                           (generate_password_hash(new_pw), session['reset_email']))
            conn.commit()
            
            # Clear sensitive ephemeral session data
            session.clear()
            flash("Security Credentials updated successfully. Please re-authenticate.", "success")
            return redirect('/admin/login')
        except Exception as e:
            flash(f"System Error: Internal database failure during credential update.", "danger")
        finally:
            conn.close()
            
    return render_template('reset_password.html')


# --- 🏁 5. EXECUTION ENGINE ---
if __name__ == '__main__':
    # Ensure vital institutional asset directories exist before deployment
    for dir_name in ['static/charts', 'static/uploads']:
        if not os.path.exists(dir_name): 
            os.makedirs(dir_name)
            
    # Deploy application in development mode
    app.run(debug=True)
