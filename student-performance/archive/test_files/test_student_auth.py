import os
import time
from db import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

def test_student_auth_logic():
    print("--- Starting Student Auth Verification ---")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    roll_no = "TEST_AUTH_001"
    default_pw = "TEST_AUTH_001@123"
    new_pw = "NewPassword123"
    
    try:
        # Cleanup
        cursor.execute("DELETE FROM students WHERE roll_no = %s", (roll_no,))
        conn.commit()
        
        # 1. Simulate Admin Adding Student (Default Password)
        pw_hash = generate_password_hash(default_pw)
        cursor.execute("""
            INSERT INTO students (roll_no, name, email, department, semester, password_hash, is_password_changed)
            VALUES (%s, 'Test User', 'test@test.com', 'MCA', '1', %s, FALSE)
        """, (roll_no, pw_hash))
        conn.commit()
        print("[OK] Student Added with Default Password")
        
        # 2. Verify Default Password Login
        cursor.execute("SELECT * FROM students WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        
        if check_password_hash(student['password_hash'], default_pw):
             print("[PASS] Default Password Hash Verification Successful")
        else:
             print("[FAIL] Default Password Verification Failed")
             
        if not student['is_password_changed']:
             print("[PASS] is_password_changed is FALSE initially")
        else:
             print("[FAIL] is_password_changed should be FALSE")
             
        # 3. Simulate Change Password
        new_hash = generate_password_hash(new_pw)
        cursor.execute("""
            UPDATE students 
            SET password_hash=%s, is_password_changed=TRUE 
            WHERE roll_no=%s
        """, (new_hash, roll_no))
        conn.commit()
        print("[OK] Password Changed to New Password")
        
        # 4. Verify New Password Login
        cursor.execute("SELECT * FROM students WHERE roll_no = %s", (roll_no,))
        student = cursor.fetchone()
        
        if check_password_hash(student['password_hash'], new_pw):
             print("[PASS] New Password Hash Verification Successful")
        else:
             print("[FAIL] New Password Verification Failed")
             
        if student['is_password_changed']:
             print("[PASS] is_password_changed is TRUE after update")
        else:
             print("[FAIL] is_password_changed should be TRUE")
             
        # Cleanup
        cursor.execute("DELETE FROM students WHERE roll_no = %s", (roll_no,))
        conn.commit()
        print("\n[OK] Cleanup Complete")
        
    except Exception as e:
        print(f"Test Failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    test_student_auth_logic()
