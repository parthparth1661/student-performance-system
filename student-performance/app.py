from flask import Flask, redirect, url_for, session
from admin_routes import admin_bp
from student_routes import student_bp
from db import init_db
import os

app = Flask(__name__)
# 1. Force Logout on App Start: Random key invalidates old sessions on restart
app.secret_key = os.urandom(24)

# Initialize database
init_db()

# Register Blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(student_bp)

@app.route('/')
def index():
    # 2. Strict Logout on Root Access
    session.clear()
    return redirect(url_for('admin.login'))

if __name__ == '__main__':
    # Ensure charts directory exists
    if not os.path.exists('static/charts'):
        os.makedirs('static/charts')
    
    app.run(debug=True)






