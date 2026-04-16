import os
import pandas as pd
from datetime import datetime, date
from db import get_db_connection
from analysis import get_working_days, process_csv

def test_gtu_logic():
    print("--- Starting GTU Logic Verification ---")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Setup Test Data
    dept = 'TEST_GTU'
    sem = '1'
    start_date = '2023-10-01' # Sunday
    end_date = '2023-10-10'   # Tuesday
    # Days: 
    # 1 (Sun) - Exclude
    # 2 (Mon) - Work
    # 3 (Tue) - Work
    # 4 (Wed) - Work
    # 5 (Thu) - Holiday (Test)
    # 6 (Fri) - Work
    # 7 (Sat) - Work
    # 8 (Sun) - Exclude
    # 9 (Mon) - Work
    # 10 (Tue) - Work
    # Total Working: 2,3,4,6,7,9,10 = 7 days.
    
    try:
        # Clear previous test data
        cursor.execute("DELETE FROM academic_calendar WHERE department=%s AND semester=%s", (dept, sem))
        cursor.execute("DELETE FROM holidays WHERE name='TEST_HOLIDAY'")
        conn.commit()
        
        # Insert Calendar
        cursor.execute("""
            INSERT INTO academic_calendar (department, semester, start_date, end_date)
            VALUES (%s, %s, %s, %s)
        """, (dept, sem, start_date, end_date))
        
        # Insert Holiday (Oct 5, 2023)
        cursor.execute("INSERT INTO holidays (holiday_date, name) VALUES ('2023-10-05', 'TEST_HOLIDAY')")
        conn.commit()
        print("[OK] Test Data Inserted")
        
        # 2. Test get_working_days
        days = get_working_days(dept, sem)
        print(f"Working Days Calculation: {days} (Expected: 7)")
        if days == 7:
            print("[PASS] Working Days Logic Correct")
        else:
            print(f"[FAIL] Working Days Logic Incorrect. Got {days}")

        # 3. Test process_csv Validation
        # Create a dummy student first
        cursor.execute("DELETE FROM students WHERE roll_no='TEST001'")
        cursor.execute("INSERT INTO students (roll_no, name, email, department, semester) VALUES ('TEST001', 'Test Student', 'test@test.com', %s, %s)", (dept, sem))
        conn.commit()
        
        # Create CSV Data
        # Row 1: Valid (2023-10-02 Mon)
        # Row 2: Sunday (2023-10-01) -> Fail
        # Row 3: Holiday (2023-10-05) -> Fail
        # Row 4: Outside (2023-09-30) -> Fail
        
        csv_data = {
            'roll_no': ['TEST001', 'TEST001', 'TEST001', 'TEST001'],
            'attendance_date': ['2023-10-02', '2023-10-01', '2023-10-05', '2023-09-30'],
            'status': ['Present', 'Present', 'Present', 'Present'],
            'remarks': ['OK', 'Sun', 'Holiday', 'Outside']
        }
        df = pd.DataFrame(csv_data)
        csv_path = 'test_attendance.csv'
        df.to_csv(csv_path, index=False)
        
        print("\nTesting CSV Upload Validation...")
        success, msg = process_csv(csv_path, dept, sem)
        print(f"Process Result: {msg}")
        
        # Verify Errors
        # We expect success_count = 1 (Row 1 only)
        # Msg should mention errors for others.
        if "Imported 1 Attendance records" in msg:
             print("[PASS] CSV Validation Logic Correct (Only 1 valid record imported)")
        else:
             print(f"[FAIL] CSV Validation Failed. Output: {msg}")
             
        # Cleanup
        if os.path.exists(csv_path):
            os.remove(csv_path)
            
        cursor.execute("DELETE FROM students WHERE roll_no='TEST001'")
        cursor.execute("DELETE FROM academic_calendar WHERE department=%s AND semester=%s", (dept, sem))
        cursor.execute("DELETE FROM holidays WHERE name='TEST_HOLIDAY'")
        conn.commit()
        print("\n[OK] Cleanup Complete")
        
    except Exception as e:
        print(f"Test Failed with Exception: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    test_gtu_logic()
