
import os
import sys
import json
import re
from flask import Flask, url_for

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app

def check_file_exists(base_path, relative_path):
    """Checks if a file exists given a base static path and a relative path."""
    # Remove 'static/' prefix if present in relative path for join
    if relative_path.startswith('static/'):
        clean_path = relative_path.replace('static/', '', 1)
    elif relative_path.startswith('/static/'):
        clean_path = relative_path.replace('/static/', '', 1)
    else:
        clean_path = relative_path
        
    full_path = os.path.join(base_path, clean_path)
    return os.path.exists(full_path), full_path

def audit_hostess_assets(app):
    print("\n--- Auditing Hostess Assets (Seeds vs Filesystem) ---")
    training_dir = os.path.join(app.root_path, 'data', 'training', 'hostesses')
    static_images_dir = os.path.join(app.static_folder, 'images', 'hostesses')
    static_videos_dir = os.path.join(app.static_folder, 'videos', 'hostesses')
    
    if not os.path.exists(training_dir):
        print(f"❌ Training directory not found: {training_dir}")
        return

    for name in os.listdir(training_dir):
        hostess_path = os.path.join(training_dir, name)
        if os.path.isdir(hostess_path):
            profile_file = os.path.join(hostess_path, 'profile.json')
            if os.path.exists(profile_file):
                try:
                    with open(profile_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Check Image
                    img_name = data.get('image')
                    if img_name:
                        # The seed might just have "layla.png" or "hostesses/layla.png"
                        # Usually it is just the filename if the code appends the path, 
                        # OR it's a relative path. 
                        # Based on typical logic: url_for('static', filename='images/hostesses/' + img_name)
                        
                        # We check if the file exists in static/images/hostesses/
                        img_path = os.path.join(static_images_dir, img_name)
                        if os.path.exists(img_path):
                            print(f"✅ [{name}] Image found: {img_name}")
                        else:
                            print(f"❌ [{name}] Image MISSING: {img_name} (Expected at: {img_path})")
                            # Suggest fix
                            # Check if a file with different extension exists
                            base_name = os.path.splitext(img_name)[0]
                            for ext in ['.png', '.jpg', '.jpeg', '.gif']:
                                if os.path.exists(os.path.join(static_images_dir, base_name + ext)):
                                    print(f"   💡 Found alternative: {base_name + ext}")
                    
                    # Check Video
                    vid_name = data.get('video')
                    if vid_name:
                        vid_path = os.path.join(static_videos_dir, vid_name)
                        if os.path.exists(vid_path):
                            print(f"✅ [{name}] Video found: {vid_name}")
                        else:
                            print(f"❌ [{name}] Video MISSING: {vid_name} (Expected at: {vid_path})")

                except Exception as e:
                    print(f"⚠️ Error reading profile for {name}: {e}")

def audit_template_assets(app):
    print("\n--- Auditing Template Static References (Basic Regex) ---")
    templates_dir = os.path.join(app.root_path, 'templates')
    
    # Regex to find url_for('static', filename='...')
    # and simple src="/static/..." or href="/static/..."
    regex_url_for = re.compile(r"url_for\s*\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]\s*\)")
    
    checked_files = set()
    
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, templates_dir)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                matches = regex_url_for.findall(content)
                for filename in matches:
                    if filename in checked_files:
                        continue
                        
                    exists, full_path = check_file_exists(app.static_folder, filename)
                    if exists:
                        # print(f"✅ Template ref found: {filename}")
                        pass
                    else:
                        print(f"❌ Template ref MISSING: {filename} (in {rel_path})")
                    
                    checked_files.add(filename)

def check_adminlte_integrity(app):
    print("\n--- Checking AdminLTE Core Files ---")
    core_files = [
        'adminlte/css/adminlte.min.css',
        'adminlte/js/adminlte.min.js',
        'plugins/bootstrap/js/bootstrap.bundle.min.js', # Often needed
        'plugins/jquery/jquery.min.js', # Often needed
        'plugins/fontawesome-free/css/all.min.css'
    ]
    
    for f in core_files:
        exists, path = check_file_exists(app.static_folder, f)
        if exists:
            print(f"✅ AdminLTE file found: {f}")
        else:
            print(f"❌ AdminLTE file MISSING: {f}")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print(f"Static Folder: {app.static_folder}")
        audit_hostess_assets(app)
        audit_template_assets(app)
        check_adminlte_integrity(app)
