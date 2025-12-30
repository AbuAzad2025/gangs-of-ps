from extensions import db
from datetime import datetime, timezone

class GameLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(128), nullable=False)
    target_id = db.Column(db.Integer, nullable=True) # ID of affected user/item
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    admin = db.relationship('User', foreign_keys=[admin_id], backref='admin_logs')

    def __repr__(self):
        return f'<GameLog {self.action} by {self.admin_id}>'
