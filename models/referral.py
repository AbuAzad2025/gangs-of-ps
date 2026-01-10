from extensions import db
from datetime import datetime, timezone

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending') # pending, completed (rewarded)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_sent')
    referred = db.relationship('User', foreign_keys=[referred_id], backref='referral_received')

    def __repr__(self):
        return f'<Referral {self.referrer_id} -> {self.referred_id}>'
