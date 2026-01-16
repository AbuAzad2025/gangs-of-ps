from utils.essentials import initialize_essentials
from extensions import socketio
from factory import create_app
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')

# Add parent directory to path to import factory and extensions
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# Ensure we're using the correct database credentials provided by the user
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/gangsofpalestine'

try:
    logging.info("Initializing Flask application...")
    app = create_app()

    # Initialize essential game data
    try:
        initialize_essentials(app)
    except Exception as e:
        logging.warning(
            f"Warning: Failed to initialize essential game data: {e}")
        # Continue anyway, as the app might still work partially
except Exception as e:
    logging.error(f"Error creating app: {e}")
    sys.exit(1)

if __name__ == '__main__':
    logging.info("Starting server on port 8080...")
    try:
        # Run without reloader to prevent double-execution issues in some
        # environments
        if socketio:
            socketio.run(app, host='0.0.0.0', port=8080, debug=False)
        else:
            app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    except OSError as e:
        if "Address already in use" in str(e):
            logging.error(
                "Error: Port 8080 is already in use. Please stop other processes.")
        else:
            logging.error(f"Error starting server: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
