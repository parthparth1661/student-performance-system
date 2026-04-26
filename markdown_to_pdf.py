#!/usr/bin/env python3
"""
Markdown to PDF Converter for SPDA Project Structure Documentation
"""

import markdown
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from reportlab.lib import colors
import re
import os

def markdown_to_pdf(markdown_file, pdf_file):
    """Convert markdown file to PDF with proper formatting"""

    # Read markdown content
    with open(markdown_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Convert markdown to HTML
    html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

    # Create PDF document
    doc = SimpleDocTemplate(pdf_file, pagesize=A4)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.darkblue,
        alignment=1  # Center alignment
    )

    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        textColor=colors.darkgreen,
        spaceBefore=20
    )

    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.darkred,
        spaceBefore=15
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=10,
        backgroundColor=colors.lightgrey,
        borderPadding=5,
        leftIndent=20,
        rightIndent=20
    )

    # Split content into sections
    story = []

    # Process HTML content
    sections = re.split(r'(<h[1-6]>.*?</h[1-6]>|<p>.*?</p>|<pre><code>.*?</code></pre>|<ul>.*?</ul>|<ol>.*?</ol>|<li>.*?</li>|<table>.*?</table>)', html_content, flags=re.DOTALL | re.IGNORECASE)

    for section in sections:
        if not section.strip():
            continue

        # Title
        if '<h1>' in section:
            title_text = re.sub(r'<[^>]+>', '', section)
            story.append(Paragraph(title_text, title_style))
            story.append(Spacer(1, 0.3*inch))

        # Heading 1
        elif '<h2>' in section:
            h1_text = re.sub(r'<[^>]+>', '', section)
            story.append(Paragraph(h1_text, heading1_style))

        # Heading 2
        elif '<h3>' in section:
            h2_text = re.sub(r'<[^>]+>', '', section)
            story.append(Paragraph(h2_text, heading2_style))

        # Code blocks
        elif '<pre><code>' in section:
            code_text = re.sub(r'<[^>]+>', '', section)
            story.append(Paragraph(code_text, code_style))
            story.append(Spacer(1, 0.1*inch))

        # Regular paragraphs
        elif '<p>' in section:
            para_text = re.sub(r'<[^>]+>', '', section)
            if para_text.strip():
                story.append(Paragraph(para_text, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))

        # Lists
        elif '<ul>' in section or '<ol>' in section:
            list_items = re.findall(r'<li>(.*?)</li>', section, re.DOTALL | re.IGNORECASE)
            for item in list_items:
                item_text = re.sub(r'<[^>]+>', '', item)
                story.append(Paragraph(f"• {item_text}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

    # Build PDF
    doc.build(story)
    print(f"PDF created successfully: {pdf_file}")

if __name__ == "__main__":
    markdown_file = r"c:\laragon\www\student-performance-system\SYSTEM_ROUTES_DETAILED_EXPLANATION.md"
    pdf_file = r"c:\laragon\www\student-performance-system\SYSTEM_ROUTES_DETAILED_EXPLANATION.pdf"

    if os.path.exists(markdown_file):
        markdown_to_pdf(markdown_file, pdf_file)
    else:
        print(f"Markdown file not found: {markdown_file}")