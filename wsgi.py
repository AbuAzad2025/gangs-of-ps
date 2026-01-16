from config import Config
from factory import create_app
import sys
import os
from dotenv import load_dotenv

# Expand the path to include the project directory
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.append(project_home)

# Load environment variables from .env file
load_dotenv(os.path.join(project_home, '.env'))

# Import the application factory

# Create the application instance
# PythonAnywhere looks for an object named 'application'
application = create_app(Config)
app = application  # Alias for compatibility with some WSGI configurations
