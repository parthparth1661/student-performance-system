import os

path = r'c:\laragon\www\student-performance-system\student-performance\admin_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Look for the duplicated # --- 👤 ADMIN PROFILE MODULE ---
indices = [i for i, line in enumerate(lines) if "# --- 👤 ADMIN PROFILE MODULE ---" in line]

if len(indices) >= 2:
    # Delete everything between indices[0] and indices[1]
    # Keep indices[1] as the valid marker
    del lines[indices[0]:indices[1]]
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Successfully cleaned up admin_routes.py.")
else:
    print(f"Markers count: {len(indices)}")
