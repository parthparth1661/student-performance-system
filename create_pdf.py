from fpdf import FPDF
import re

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Frontend-Backend Connection Documentation', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

def create_pdf_from_markdown(md_file, pdf_file):
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Create PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Split content into sections
    lines = content.split('\n')
    current_section = ""
    in_code_block = False
    code_content = []

    for line in lines:
        # Handle headers
        if line.startswith('# '):
            if current_section:
                pdf.chapter_body(current_section.strip())
                current_section = ""
            title = line[2:].strip()
            pdf.chapter_title(title)
        elif line.startswith('## '):
            if current_section:
                pdf.chapter_body(current_section.strip())
                current_section = ""
            subtitle = line[3:].strip()
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, subtitle, 0, 1, 'L')
            pdf.ln(2)
        elif line.startswith('### '):
            if current_section:
                pdf.chapter_body(current_section.strip())
                current_section = ""
            subsubtitle = line[4:].strip()
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(0, 6, subsubtitle, 0, 1, 'L')
            pdf.ln(2)
        elif line.startswith('```'):
            if in_code_block:
                # End of code block
                code_text = '\n'.join(code_content)
                pdf.set_font('Courier', '', 9)
                pdf.multi_cell(0, 4, code_text)
                pdf.ln(2)
                pdf.set_font('Arial', '', 10)
                in_code_block = False
                code_content = []
            else:
                # Start of code block
                in_code_block = True
        elif in_code_block:
            code_content.append(line)
        elif line.strip() == '':
            if current_section:
                pdf.chapter_body(current_section.strip())
                current_section = ""
        else:
            current_section += line + '\n'

    # Add remaining content
    if current_section:
        pdf.chapter_body(current_section.strip())

    # Save PDF
    pdf.output(pdf_file)
    print(f'PDF created successfully: {pdf_file}')

if __name__ == '__main__':
    create_pdf_from_markdown('frontend_backend_connection_explanation.md', 'frontend_backend_connection_explanation.pdf')