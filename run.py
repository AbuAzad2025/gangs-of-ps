
import eventlet
eventlet.monkey_patch()

from factory import create_app, db
from extensions import socketio
import os
from config import Config, TestConfig
import click
from flask.cli import with_appcontext

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

@app.cli.command("economy_daily")
@with_appcontext
def economy_daily():
    from services.economy import process_daily_economy_checks
    """Runs the daily economy checks (bank fees, property maintenance)."""
    app.logger.info("Starting daily economy checks...")
    process_daily_economy_checks()
    app.logger.info("Daily economy checks completed!")

if __name__ == '__main__':
    # Create tables automatically on dev run
    # with app.app_context():
    #     db.create_all()
    app.logger.info("Starting Flask Server...")
    if socketio:
        socketio.run(app, debug=True, port=8000)
    else:
        app.run(debug=True, port=8000, use_reloader=True, threaded=True)
