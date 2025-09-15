import sys
import json
import os
import uuid
from .utils import pdf_to_text
from .chunk import chunk_text
from .extractor import generate_rule_json

def main(file_path):
    print(f"Processing file: {file_path}")
    
    text = pdf_to_text(file_path)
    chunks, pdf_sections = chunk_text(text, return_sections=True)
    print(f"Document chunked into {len(chunks)} chunks.")
    
    all_rules = []
    for idx, chunk in enumerate(chunks):
        print(f"Extracting rules from chunk {idx+1}/{len(chunks)}...")
        section_heading = pdf_sections[idx] if pdf_sections and idx < len(pdf_sections) else "General"
        rules_json = generate_rule_json(
            chunk,
            pdf_sections=section_heading,
            source_document=file_path
        )
        rules = json.loads(rules_json)
        all_rules.extend(rules)
    
    # Assign unique rule_id across all rules
    for rule in all_rules:
        rule["rule_id"] = str(uuid.uuid4())
    
    # Save combined output
    out_file = file_path.rsplit(".", 1)[0] + "_rules.json"
    with open(out_file, "w") as f:
        json.dump(all_rules, f, indent=2)
    print(f"Rule extraction completed. Output saved to {out_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path-to-pdf>")
    else:
        main(sys.argv[1])