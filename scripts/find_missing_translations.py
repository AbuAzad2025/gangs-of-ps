
import os
import re
import ast
import sys
from typing import Dict, List, Set, Tuple

# Paths relative to repository root
TRANSLATION_FILE = os.path.join('scripts', 'update_final_translations.py')
TEMPLATES_DIR = os.path.join('templates')
PO_FILE = os.path.join('translations', 'en', 'LC_MESSAGES', 'messages.po')

def get_existing_translations():
    try:
        # Try importing directly
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from update_final_translations import TRANSLATIONS
        return TRANSLATIONS
    except ImportError:
        # Fallback to parsing if import fails (though it shouldn't)
        print("Could not import TRANSLATIONS, attempting parse...")
        pass
    except Exception as e:
        print(f"Error importing TRANSLATIONS: {e}")
        
    with open(TRANSLATION_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the dictionary using ast
    # We look for "TRANSLATIONS = {" and the closing "}"
    # Use non-greedy match to avoid capturing subsequent code
    match = re.search(r'TRANSLATIONS\s*=\s*({.*?})\n', content, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group(1))
        except Exception as e:
            print(f"Error parsing existing translations: {e}")
            return {}
    return {}

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def load_po_translations(po_path: str = PO_FILE) -> Dict[str, str]:
    """
    Minimal parser for .po to map msgid -> msgstr.
    Handles single and multi-line strings.
    """
    if not os.path.isfile(po_path):
        return {}
    msg_map: Dict[str, str] = {}
    current_id: List[str] = []
    current_str: List[str] = []
    state = None  # 'id' or 'str' or None
    with open(po_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('msgid '):
                # flush previous
                if current_id:
                    msgid = ''.join(current_id)
                    msgstr = ''.join(current_str)
                    msg_map[msgid] = msgstr
                current_id = []
                current_str = []
                state = 'id'
                s = line[len('msgid '):].strip()
                current_id.append(_unquote_po(s))
            elif line.startswith('msgstr '):
                state = 'str'
                s = line[len('msgstr '):].strip()
                current_str.append(_unquote_po(s))
            elif line.startswith('"'):
                if state == 'id':
                    current_id.append(_unquote_po(line.strip()))
                elif state == 'str':
                    current_str.append(_unquote_po(line.strip()))
            else:
                state = None
        # flush last
        if current_id:
            msgid = ''.join(current_id)
            msgstr = ''.join(current_str)
            msg_map[msgid] = msgstr
    return msg_map

def _unquote_po(s: str) -> str:
    # remove leading/trailing quotes if present
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    # Unescape PO string format
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')

def scan_templates():
    existing_keys = set(get_existing_translations().keys())
    po_map = load_po_translations()
    po_msgids = set(po_map.keys())
    po_empty = {k for k, v in po_map.items() if v.strip() == ""}

    new_strings = {}  # Map path -> set of strings
    missing_in_po = {}  # Map path -> set of wrapped strings missing in po
    unwrapped_strings = {}  # Map path -> set of Arabic strings not wrapped

    # Regex to find Arabic text sequences in templates
    
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
            
            # Find all Arabic strings (at least 2 chars), allowing spaces and common punctuation
            matches = re.findall(r'[\u0600-\u06FF][\u0600-\u06FF\s0-9\.\-\!\؟\،\:]*[\u0600-\u06FF]', content)

            # Detect wrapped strings via _('...') and {% trans %} blocks
            wrapped_calls = set()
            # Improved regex to handle mixed quotes (e.g. _('text "quoted" text'))
            # We don't enforce closing ) immediately to allow for arguments like _('msg', arg=val)
            for mobj in re.finditer(r'_\(\s*(?P<quote>["\'])(.*?)(?P=quote)', content, flags=re.DOTALL):
                text = mobj.group(2)
                if is_arabic(text):
                    wrapped_calls.add(text.strip())
            
            for block in re.finditer(r'\{%+\s*trans\s*%}(.*?){%+\s*endtrans\s*%}', content, flags=re.DOTALL):
                # Extract Arabic chunks inside trans blocks
                inner = block.group(1)
                for m in re.findall(r'[\u0600-\u06FF][\u0600-\u06FF\s0-9\.\-\!\؟\،\:]*[\u0600-\u06FF]', inner):
                    wrapped_calls.add(m.strip())
            
            for m in matches:
                m = m.strip()
                if len(m) < 2: continue
                # Clean up jinja tags if caught accidentally (rare with this regex but possible)
                if '{{' in m or '{%' in m: continue 
                
                # Aggregate all strings
                if folder not in new_strings:
                    new_strings[folder] = set()
                new_strings[folder].add(m)

                # Classify wrapping and po coverage
                is_wrapped = False
                if m in wrapped_calls:
                    is_wrapped = True
                else:
                    # Check if m is a substring of any wrapped call (to handle punctuation differences)
                    for w in wrapped_calls:
                        if m in w:
                            is_wrapped = True
                            break
                
                if is_wrapped:
                    # Check if the wrapping call is in PO
                    covered_by_po = False
                    
                    # Check all wrapping calls that contain m
                    parent_wrappers = [w for w in wrapped_calls if m in w]
                    
                    # If ANY of the parent wrappers is in PO, we consider m covered?
                    # Ideally ALL should be, but usually m appears once per context.
                    # If m is in multiple wrappers, and one is missing, we should report it.
                    
                    all_parents_in_po = True
                    missing_parents = set()
                    
                    for w in parent_wrappers:
                        if w not in po_msgids:
                            all_parents_in_po = False
                            missing_parents.add(w)
                    
                    if parent_wrappers and all_parents_in_po:
                        covered_by_po = True
                    
                    if not covered_by_po:
                         # Add missing parents
                         if missing_parents:
                             for w in missing_parents:
                                 missing_in_po.setdefault(folder, set()).add(w)
                         else:
                             # Should not happen if is_wrapped is True
                             missing_in_po.setdefault(folder, set()).add(m)
                else:
                    unwrapped_strings.setdefault(folder, set()).add(m)

    return {
        "all_strings": new_strings,
        "missing_in_po": missing_in_po,
        "unwrapped": unwrapped_strings,
        "po_empty": list(sorted(po_empty)),
    }

def append_missing_to_po(missing_map: Dict[str, Set[str]], po_path: str = PO_FILE) -> int:
    """
    Append missing msgid entries to messages.po with empty msgstr.
    Returns number of entries appended.
    """
    if not missing_map:
        return 0
    # Flatten and de-duplicate
    to_add: List[str] = sorted({s for v in missing_map.values() for s in v})
    if not to_add:
        return 0
    with open(po_path, 'a', encoding='utf-8') as f:
        f.write("\n# Added by translation audit\n")
        for s in to_add:
            f.write(f'msgid "{s}"\n')
            f.write('msgstr ""\n\n')
    return len(to_add)

def list_endpoints():
    # Add parent directory to path dynamically
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from factory import create_app
    except Exception as e:
        print(f"Error importing app factory: {e}")
        return []
    if not os.environ.get('DATABASE_URL'):
        os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'
    try:
        app = create_app()
    except Exception as e:
        print(f"Error creating app: {e}")
        return []
    routes = []
    with app.app_context():
        for rule in app.url_map.iter_rules():
            routes.append({
                "endpoint": rule.endpoint,
                "methods": sorted(list(rule.methods)),
                "rule": str(rule)
            })
    return sorted(routes, key=lambda r: r["endpoint"])

if __name__ == "__main__":
    import json
    result = scan_templates()
    endpoints = list_endpoints()
    # Build summary
    all_strings_count = sum(len(v) for v in result["all_strings"].values())
    missing_in_po_count = sum(len(v) for v in result["missing_in_po"].values()) if result["missing_in_po"] else 0
    unwrapped_count = sum(len(v) for v in result["unwrapped"].values()) if result["unwrapped"] else 0
    print(f"Templates Arabic strings: {all_strings_count}")
    print(f"Wrapped but missing in PO: {missing_in_po_count}")
    print(f"Unwrapped Arabic strings: {unwrapped_count}")
    print(f"Total endpoints: {len(endpoints)}")
    report = {
        "summary": {
            "templates_arabic_strings": all_strings_count,
            "wrapped_missing_in_po": missing_in_po_count,
            "unwrapped_arabic_strings": unwrapped_count,
            "po_empty_entries": len(result["po_empty"]),
            "total_endpoints": len(endpoints),
        },
        "endpoints": endpoints,
        "templates": {
            "all_strings": {k: sorted(list(v)) for k, v in result["all_strings"].items()},
            "missing_in_po": {k: sorted(list(v)) for k, v in result["missing_in_po"].items()},
            "unwrapped": {k: sorted(list(v)) for k, v in result["unwrapped"].items()},
        },
        "po_empty": result["po_empty"],
    }
    with open('translation_audit_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Wrote translation audit report: translation_audit_report.json")
    # Optional fix mode
    if '--fix-po' in sys.argv:
        added = append_missing_to_po(result["missing_in_po"])
        print(f"Appended {added} missing msgid entries to {PO_FILE}")
