
import os
import re
import ast

# Path to the existing translation file
TRANSLATION_FILE = r'd:\gang of Ps\GangsOfPalestine\scripts\update_final_translations.py'
TEMPLATES_DIR = r'd:\gang of Ps\GangsOfPalestine\templates'

def get_existing_translations():
    with open(TRANSLATION_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the dictionary using ast
    # We look for "TRANSLATIONS = {" and the closing "}"
    match = re.search(r'TRANSLATIONS\s*=\s*({.*})', content, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group(1))
        except Exception as e:
            print(f"Error parsing existing translations: {e}")
            return {}
    return {}

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def scan_templates():
    existing_keys = set(get_existing_translations().keys())
    new_strings = {} # Map path -> list of strings

    # Regex to find text between tags or in attributes, naive approach
    # We look for Arabic text sequences
    
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if not file.endswith('.html'):
                continue
            
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, TEMPLATES_DIR)
            folder = os.path.dirname(rel_path)
            if folder == '':
                folder = 'General'
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all arabic strings
            # This regex looks for 2 or more consecutive Arabic characters, allowing spaces in between
            matches = re.findall(r'[\u0600-\u06FF][\u0600-\u06FF\s0-9\.\-\!\؟\،]*[\u0600-\u06FF]', content)
            
            for m in matches:
                m = m.strip()
                if len(m) < 2: continue
                # Clean up jinja tags if caught accidentally (rare with this regex but possible)
                if '{{' in m or '{%' in m: continue 
                
                if m not in existing_keys:
                    if folder not in new_strings:
                        new_strings[folder] = set()
                    new_strings[folder].add(m)

    return new_strings

if __name__ == "__main__":
    import json
    new_data = scan_templates()
    
    # Flatten the list
    all_new_keys = set()
    for strings in new_data.values():
        all_new_keys.update(strings)
        
    print(f"Found {len(all_new_keys)} unique new Arabic strings.")
    
    with open('found_translations.json', 'w', encoding='utf-8') as f:
        json.dump(list(all_new_keys), f, ensure_ascii=False, indent=2)
