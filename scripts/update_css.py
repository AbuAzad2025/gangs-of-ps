import re
import os

file_path = r'd:\gang of Ps\GangsOfPalestine\templates\base.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to match the specific style block we want to replace
# We look for <style> followed by :root to be sure we get the right one
pattern = r'<style>\s*:root \{.*?</style>'

replacement = """<!-- Custom Luxury CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/palestine_luxury.css') }}">"""

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content != content:
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully replaced style block with CSS link.")
else:
    print("Pattern not found or no change made.")
