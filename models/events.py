from extensions import db
from datetime import datetime, timezone

class WeeklyWinner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    week_number = db.Column(db.Integer, nullable=False) # e.g., week number of the year
    year = db.Column(db.Integer, nullable=False)
    amount_won = db.Column(db.Integer, default=100) # $100
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship to access user details
    user = db.relationship('User', backref=db.backref('wins', lazy=True))

    def __repr__(self):
        return f'<WeeklyWinner {self.user_id} - Week {self.week_number}>'
