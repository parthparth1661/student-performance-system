from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import re

def create_simple_pdf(md_file, pdf_file):
    import re
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Create PDF document
    doc = SimpleDocTemplate(pdf_file, pagesize=letter,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=20,
        textColor='#333333'
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=15,
        textColor='#555555'
    )

    h3_style = ParagraphStyle(
        'H3',
        parent=styles['Heading3'],
        fontSize=11,
        spaceAfter=10,
        textColor='#666666'
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        leftIndent=20,
        spaceAfter=10
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8
    )

    story = []

    # Add title
    story.append(Paragraph("Frontend-Backend Connection Documentation", title_style))
    story.append(Spacer(1, 20))

    # Split content into sections
    lines = content.split('\n')
    current_paragraph = ""
    in_code_block = False
    code_lines = []

    for line in lines:
        line = line.rstrip()

        if line.startswith('# '):
            # Main title (already added)
            continue
        elif line.startswith('## '):
            if current_paragraph:
                story.append(Paragraph(current_paragraph, normal_style))
                current_paragraph = ""
            title = line[3:].strip()
            story.append(Paragraph(title, h1_style))
        elif line.startswith('### '):
            if current_paragraph:
                story.append(Paragraph(current_paragraph, normal_style))
                current_paragraph = ""
            subtitle = line[4:].strip()
            story.append(Paragraph(subtitle, h2_style))
        elif line.startswith('```'):
            if in_code_block:
                # End code block
                code_text = '\n'.join(code_lines)
                # Clean up HTML tags for plain text
                import re
                code_text = re.sub(r'<[^>]+>', '', code_text)
                story.append(Paragraph(code_text, code_style))
                in_code_block = False
                code_lines = []
            else:
                # Start code block
                if current_paragraph:
                    story.append(Paragraph(current_paragraph, normal_style))
                    current_paragraph = ""
                in_code_block = True
        elif in_code_block:
            # Remove HTML tags from code lines
            clean_line = re.sub(r'<[^>]+>', '', line)
            code_lines.append(clean_line)
        elif line.strip() == '':
            if current_paragraph:
                story.append(Paragraph(current_paragraph, normal_style))
                current_paragraph = ""
        else:
            # Remove HTML tags from regular lines
            clean_line = re.sub(r'<[^>]+>', '', line)
            if current_paragraph:
                current_paragraph += ' ' + clean_line
            else:
                current_paragraph = clean_line

    # Add remaining content
    if current_paragraph:
        story.append(Paragraph(current_paragraph, normal_style))

    # Build PDF
    doc.build(story)
    print(f'PDF created successfully: {pdf_file}')

if __name__ == '__main__':
    create_simple_pdf('frontend_backend_connection_explanation.md', 'frontend_backend_connection_explanation.pdf')