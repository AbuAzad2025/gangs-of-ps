from extensions import db
from datetime import datetime, timezone

class Race(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='waiting') # waiting, in_progress, finished
    bet_amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    participants = db.relationship('RaceParticipant', backref='race', lazy=True, cascade="all, delete-orphan")
    creator = db.relationship('User', foreign_keys=[creator_id])

class RaceParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    user_vehicle_id = db.Column(db.Integer, db.ForeignKey('user_vehicle.id'), nullable=False, index=True)
    
    score = db.Column(db.Float, default=0.0)
    rank = db.Column(db.Integer, nullable=True) # 1, 2, 3...
    reward = db.Column(db.Integer, default=0)
    
    user = db.relationship('User')
    user_vehicle = db.relationship('UserVehicle')
