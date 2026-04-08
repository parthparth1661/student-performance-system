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


if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






