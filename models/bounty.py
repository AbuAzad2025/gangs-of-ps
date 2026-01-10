from extensions import db
from datetime import datetime, timezone

class Bounty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_anonymous = db.Column(db.Boolean, default=False)

    placer = db.relationship('User', foreign_keys=[placer_id], backref='placed_bounties')
    target = db.relationship('User', foreign_keys=[target_id], backref='bounties_on_me')

    def __repr__(self):
        return f'<Bounty {self.amount} on {self.target_id}>'
