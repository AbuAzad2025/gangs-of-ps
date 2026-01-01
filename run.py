
from factory import create_app, db
import click
from flask.cli import with_appcontext

app = create_app()

@app.cli.command("seed_db")
@with_appcontext
def seed_db():
    from utils.essentials import initialize_essentials
    """Seeds the database with initial data using the centralized initialization logic."""
    db.create_all()
    
    # Use the centralized initialization function
    initialize_essentials(app)
    
    print("Database seeding completed!")

@app.cli.command("economy_daily")
@with_appcontext
def economy_daily():
    from services.economy import process_daily_economy_checks
    """Runs the daily economy checks (bank fees, property maintenance)."""
    print("Starting daily economy checks...")
    process_daily_economy_checks()
    print("Daily economy checks completed!")

if __name__ == '__main__':
    # Create tables automatically on dev run
    # with app.app_context():
    #     db.create_all()
    print("Starting Flask Server...", flush=True)
    app.run(debug=True, port=8080, use_reloader=True, threaded=True)
