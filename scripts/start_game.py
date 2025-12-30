import os
import sys

# Add parent directory to path to import factory and extensions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app
from utils.essentials import initialize_essentials

# Ensure we're using the correct database credentials provided by the user
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'

try:
    print("Initializing Flask application...", flush=True)
    app = create_app()
    
    # Initialize essential game data
    try:
        initialize_essentials(app)
    except Exception as e:
        print(f"Warning: Failed to initialize essential game data: {e}", flush=True)
        # Continue anyway, as the app might still work partially
except Exception as e:
    print(f"Error creating app: {e}", flush=True)
    sys.exit(1)

if __name__ == '__main__':
    print("Starting server on port 8080...", flush=True)
    try:
        # Run without reloader to prevent double-execution issues in some environments
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            print("Error: Port 8080 is already in use. Please stop other processes.", flush=True)
        else:
            print(f"Error starting server: {e}", flush=True)
    except Exception as e:
        print(f"Unexpected error: {e}", flush=True)
