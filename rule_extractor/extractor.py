import os
from dotenv import load_dotenv
from openai import OpenAI
 
import json
from datetime import datetime

load_dotenv() 

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

client = OpenAI(api_key=api_key)

ALLOWED_CATEGORIES = ["Marketing", "Gambling", "Legal", "Compliance"]

def load_prompt(path):
    base_dir = os.path.dirname(__file__)
    absolute_path = os.path.join(base_dir, path)
    with open(absolute_path, 'r') as f:
        return f.read()

def postprocess_rules(rules, section_heading=None, source_document=None):
    extraction_time = datetime.now().isoformat()
    enriched = []
    for rule in rules:
        enriched_rule = {
            "rule_text": rule.get("rule_text", ""),
            "context": rule.get("context", ""),
            "tags": sorted(set(tag.lower() for tag in rule.get("tags", []))),
            "category": rule.get("category", ""),
            "metadata": {
                "extraction_timestamp": extraction_time,
                "source_document": os.path.splitext(os.path.basename(source_document or ""))[0]
            }
        }
        enriched.append(enriched_rule)
    return enriched

def classify_category(rule_text: str) -> str:
    """Use the LLM to strictly classify rule_text into one of ALLOWED_CATEGORIES."""
    instruction = (
        "Classify the following rule into exactly one category from this set: "
        + ", ".join(ALLOWED_CATEGORIES)
        + ". Respond with only the single category word, nothing else.\n\nRule:\n"
        + rule_text
    )
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a precise classifier."},
                {"role": "user", "content": instruction},
            ],
            max_completion_tokens=10,
            n=1,
        )
        label = (response.choices[0].message.content or "").strip()
        for allowed in ALLOWED_CATEGORIES:
            if label.lower() == allowed.lower():
                return allowed
        text = rule_text.lower()
        if any(k in text for k in ["advert", "marketing", "promotion", "brand"]):
            return "Marketing"
        if any(k in text for k in ["gambl", "bet", "wager", "lottery"]):
            return "Gambling"
        if any(k in text for k in ["law", "legal", "contract", "clause", "statute"]):
            return "Legal"
        return "Compliance"
    except Exception:
        text = rule_text.lower()
        if any(k in text for k in ["advert", "marketing", "promotion", "brand"]):
            return "Marketing"
        if any(k in text for k in ["gambl", "bet", "wager", "lottery"]):
            return "Gambling"
        if any(k in text for k in ["law", "legal", "contract", "clause", "statute"]):
            return "Legal"
        return "Compliance"

def is_complex_rule(rule):
    # Example: mark as complex if rule_text is very long or has many conjunctions
    rule_text = rule.get("rule_text", "")
    if len(rule_text.split()) > 60:
        return True
    if rule_text.count(" and ") + rule_text.count(" or ") > 3:
        return True
    return False

def extract_rules_with_model(chunk_text, section_heading, source_document, model):
    base_prompt = load_prompt("prompts/base_prompt.txt")
    prompt = f"{base_prompt}\n\nText:\n{chunk_text}\n\nOutput:"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful rule extraction assistant."},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=4000,
        n=1
    )
    llm_output = response.choices[0].message.content
    rules = json.loads(llm_output)
    for r in rules:
        if not r.get("category"):
            r["category"] = classify_category(r.get("rule_text", ""))
    return postprocess_rules(
        rules,
        section_heading=section_heading,
        source_document=source_document
    )

def generate_rule_json(chunk_text, pdf_sections=None, source_document=None):
    """
    Calls LLM for rule extraction, then enriches with category and metadata.
    If a rule is too complex, re-extracts it using gpt-5.
    pdf_sections should be a string (section heading) for this chunk.
    """
    # First pass: gpt-5-mini
    rules = extract_rules_with_model(
        chunk_text,
        section_heading=pdf_sections,
        source_document=source_document,
        model="gpt-5-mini"
    )

    # Second pass: gpt-5 for complex rules
    improved_rules = []
    for rule in rules:
        if is_complex_rule(rule):
            print("Re-extracting complex rule with gpt-5...")
            # Re-extract just this rule's text with gpt-5
            single_rule_text = rule["rule_text"]
            # Use the same prompt but with only the complex rule text
            refined = extract_rules_with_model(
                single_rule_text,
                section_heading=rule.get("category", pdf_sections),
                source_document=source_document,
                model="gpt-5"
            )
            # If gpt-5 returns multiple rules, flatten them in place of the original
            improved_rules.extend(refined)
        else:
            improved_rules.append(rule)
    return json.dumps(improved_rules, indent=2)