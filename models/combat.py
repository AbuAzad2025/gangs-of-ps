from extensions import db
from datetime import datetime, timezone

class CombatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attacker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    defender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    money_stolen = db.Column(db.Integer, default=0)
    exp_gain = db.Column(db.Integer, default=0)
    is_attacker_anonymous = db.Column(db.Boolean, default=False)
    
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    attacker = db.relationship('User', foreign_keys=[attacker_id], backref='attacks_made')
    defender = db.relationship('User', foreign_keys=[defender_id], backref='attacks_received')
    winner = db.relationship('User', foreign_keys=[winner_id])

    def __repr__(self):
        return f'<CombatLog {self.attacker_id} vs {self.defender_id} at {self.timestamp}>'

class ActiveIntel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False) # When intel becomes available (after delivery)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='active_intel')
    target = db.relationship('User', foreign_keys=[target_id])

    def __repr__(self):
        return f'<ActiveIntel {self.user_id} -> {self.target_id}>'
