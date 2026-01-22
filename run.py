import os
import sys

# Detect if we are running in a CLI environment (migrations, seeding, etc.)
# or if we are running on PythonAnywhere (where we shouldn't use eventlet)
is_cli = 'flask' in sys.argv[0] or 'db' in sys.argv
is_pythonanywhere = 'PYTHONANYWHERE_DOMAIN' in os.environ

# Only apply eventlet monkey patch if:
# 1. We are NOT running a CLI command (like flask db migrate)
# 2. We are NOT on PythonAnywhere (which uses WSGI and conflicts with eventlet)
if not is_cli and not is_pythonanywhere:
    try:
        import eventlet
        eventlet.monkey_patch()
    except ImportError:
        pass

from flask.cli import with_appcontext
from config import Config, TestConfig
from extensions import socketio
from factory import create_app, db


cfg = TestConfig if os.environ.get("USE_TEST_DB") == "1" else Config
app = create_app(cfg)


@app.cli.command("seed_db")
@with_appcontext
def seed_db():
    from utils.essentials import initialize_essentials
    """Seeds the database with initial data using the centralized initialization logic."""
    db.create_all()

    # Use the centralized initialization function
    initialize_essentials(app)

    app.logger.info("Database seeding completed!")


@app.cli.command("seed_daily_tasks")
@with_appcontext
def seed_daily_tasks():
    from utils.essentials import initialize_daily_tasks
    db.create_all()
    initialize_daily_tasks()
    db.session.commit()
    app.logger.info("Daily tasks seeding completed!")


@app.cli.command("economy_daily")
@with_appcontext
def economy_daily():
    from services.economy import process_daily_economy_checks
    """Runs the daily economy checks (bank fees, property maintenance)."""
    app.logger.info("Starting daily economy checks...")
    process_daily_economy_checks()
    app.logger.info("Daily economy checks completed!")


if __name__ == '__main__':
    app.logger.info("Starting Flask Server...")
    # Run with SocketIO only locally and if not CLI
    if socketio and not is_cli and not is_pythonanywhere:
        socketio.run(app, debug=True, port=8000)
    else:
        # Fallback for CLI or PythonAnywhere
        app.run(debug=True, port=8000, use_reloader=True, threaded=True)
