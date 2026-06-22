import io
import re
from pdfminer.high_level import extract_text

def extract_text_from_pdf(file_bytes: bytes):
    pdf_file = io.BytesIO(file_bytes)
    text = extract_text(pdf_file)
    
    # Double character fix: "wwoorrdd" → "word"
    text = re.sub(r'(.)\1+', r'\1', text)
    
    return text