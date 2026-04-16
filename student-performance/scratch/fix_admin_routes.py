import os

path = r'c:\laragon\www\student-performance-system\student-performance\admin_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the reset_data route
start_line = -1
for i, line in enumerate(lines):
    if "@admin_bp.route('/reset-data')" in line:
        start_line = i
        break

if start_line != -1:
    # Find the start of admin profile module
    end_line = -1
    for i, line in enumerate(lines[start_line:], start_line):
        if "# --- 👤 ADMIN PROFILE MODULE ---" in line and i > start_line + 5:
            end_line = i
            break
    
    if end_line != -1:
        new_reset_data = [
            "@admin_bp.route('/reset-data')\n",
            "def reset_data():\n",
            "    # Only reset dynamic data (not admin)\n",
            "    conn = get_db_connection()\n",
            "    cursor = conn.cursor()\n",
            "    try:\n",
            "        cursor.execute(\"SET FOREIGN_KEY_CHECKS = 0\")\n",
            "        tables = ['attendance', 'marks', 'subjects', 'students', 'faculty']\n",
            "        for table in tables:\n",
            "            cursor.execute(f\"TRUNCATE TABLE {table}\")\n",
            "        cursor.execute(\"SET FOREIGN_KEY_CHECKS = 1\")\n",
            "        conn.commit()\n",
            "        flash(\"All system data has been safely reset.\", \"success\")\n",
            "    except Exception as e:\n",
            "        flash(f\"Error resetting data: {e}\", \"danger\")\n",
            "    finally:\n",
            "        conn.close()\n",
            "    return redirect(url_for('admin.dashboard'))\n",
            "\n",
            "\n"
        ]
        
        # Replace the messy section
        lines[start_line:end_line] = new_reset_data
        
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("Successfully fixed admin_routes.py using python script.")
    else:
        print("End line not found.")
else:
    print("Start line not found.")
