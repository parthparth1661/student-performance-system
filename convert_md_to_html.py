import markdown
from pathlib import Path

# Read markdown file
with open('frontend_backend_connection_explanation.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

# Convert to HTML
html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code', 'codehilite'])

# Add basic styling
html_template = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Frontend-Backend Connection Documentation</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        h1 { color: #333; border-bottom: 2px solid #6366f1; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        h3 { color: #666; }
        code { background: #f4f4f4; padding: 2px 4px; border-radius: 4px; font-family: 'Courier New', monospace; }
        pre { background: #f4f4f4; padding: 15px; border-radius: 8px; overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .highlight { background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 20px 0; }
        blockquote { border-left: 4px solid #6366f1; padding-left: 15px; margin: 20px 0; color: #666; }
    </style>
</head>
<body>
''' + html_content + '''
</body>
</html>
'''

# Write HTML file
with open('frontend_backend_connection_explanation.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print('HTML file created successfully')