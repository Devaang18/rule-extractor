import fitz 

def pdf_to_text(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = []
    for page in doc:
        text = page.get_text("text")
        full_text.append(text)
    return "\n".join(full_text)
