from db import get_db_connection

def update_admin_table():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return

    cursor = conn.cursor()
    
    try:
        # check if columns exist before adding to avoid errors on re-run
        cursor.execute("DESCRIBE admins")
        columns = [row[0] for row in cursor.fetchall()]
        
        alter_query = "ALTER TABLE admins "
        add_columns = []
        
        if 'full_name' not in columns:
            add_columns.append("ADD COLUMN full_name VARCHAR(100)")
        
        if 'email' not in columns:
            add_columns.append("ADD COLUMN email VARCHAR(100)")
            
        if 'profile_image' not in columns:
            add_columns.append("ADD COLUMN profile_image VARCHAR(255)")
            
        if 'updated_at' not in columns:
            add_columns.append("ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            
        if 'created_at' not in columns:
            add_columns.append("ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            
        if add_columns:
            alter_query += ", ".join(add_columns)
            print(f"Executing: {alter_query}")
            cursor.execute(alter_query)
            conn.commit()
            print("Admins table updated successfully.")
        else:
            print("Admins table already has all required columns.")

        # Create Academic Calendar Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS academic_calendar (
                id INT AUTO_INCREMENT PRIMARY KEY,
                department VARCHAR(50) NOT NULL,
                semester VARCHAR(20) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                UNIQUE KEY unique_term (department, semester)
            )
        """)
        print("Academic Calendar table checked/created.")

        # Create Holidays Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS holidays (
                id INT AUTO_INCREMENT PRIMARY KEY,
                holiday_date DATE NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL
            )
        """)
        print("Holidays table checked/created.")

        # Update Students Table for Login
        cursor.execute("DESCRIBE students")
        student_cols = [row[0] for row in cursor.fetchall()]
        
        alter_students = "ALTER TABLE students "
        add_student_cols = []
        
        if 'password_hash' not in student_cols:
            add_student_cols.append("ADD COLUMN password_hash VARCHAR(255)")
            
        if 'is_password_changed' not in student_cols:
            add_student_cols.append("ADD COLUMN is_password_changed BOOLEAN DEFAULT FALSE")
            
        if add_student_cols:
            alter_students += ", ".join(add_student_cols)
            print(f"Executing: {alter_students}")
            cursor.execute(alter_students)
            conn.commit()
            print("Students table updated for login.")
        else:
            print("Students table already has login columns.")

    except Exception as e:
        print(f"Error updating table: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_admin_table()
