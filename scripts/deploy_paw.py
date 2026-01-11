import os
import sys
import subprocess
import shutil

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

def run_command(command, cwd=None):
    """Run a shell command."""
    print(f"Running: {command}")
    try:
        subprocess.check_call(command, shell=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(e)
        sys.exit(1)

def main():
    print("=== PythonAnywhere Deployment Script ===")
    
    # 1. Check for .env file
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        print("Creating .env file from .env.example (if available) or defaults...")
        # You might want to create a default .env here if needed
        # For now, let's just warn
        print("WARNING: .env file not found. Ensure you have configured environment variables.")
        # Create a basic .env if it doesn't exist
        with open(env_path, 'w') as f:
            f.write("FLASK_APP=run.py\n")
            f.write("FLASK_DEBUG=0\n")
            f.write("SECRET_KEY=change_this_to_something_secure\n")
            # Default to SQLite for safety, but user should change to MySQL/Postgres on PAW
            f.write("DATABASE_URL=sqlite:///app.db\n") 
        print("Created basic .env file. Please edit it with your database credentials.")
    
    # 2. Install dependencies (Optional, PAW usually does this via console)
    # print("Installing dependencies...")
    # run_command("pip install -r requirements.txt", cwd=project_root)
    
    # 3. Initialize/Upgrade Database
    print("Initializing/Upgrading Database...")
    # Initialize migrations if not exists
    migrations_dir = os.path.join(project_root, 'migrations')
    if not os.path.exists(migrations_dir):
        print("Initializing migrations folder...")
        run_command("flask db init", cwd=project_root)
    
    # Generate migration (might fail if no changes, which is fine)
    try:
        print("Generating migration...")
        run_command("flask db migrate -m 'Initial migration'", cwd=project_root)
    except:
        print("Migration generation failed or no changes detected. Continuing...")
        
    # Apply upgrades
    print("Applying upgrades...")
    run_command("flask db upgrade", cwd=project_root)
    
    # 4. Seed Database
    print("Seeding Database...")
    run_command("flask seed_db", cwd=project_root)
    
    # 5. Collect Static Files (Optional, for PAW static file mapping)
    # PAW requires you to map /static to the static folder manually in the web tab.
    
    print("\n=== Deployment Setup Complete ===")
    print("Next Steps:")
    print("1. Go to PythonAnywhere Web Tab.")
    print("2. Set 'Source code' to: " + project_root)
    print("3. Set 'WSGI configuration file' to point to: " + os.path.join(project_root, 'wsgi.py'))
    print("4. Create a Virtualenv and install requirements.")
    print("5. Configure Static Files mapping:")
    print("   URL: /static/")
    print("   Directory: " + os.path.join(project_root, 'static'))
    print("6. Reload the Web App.")

if __name__ == "__main__":
    main()
