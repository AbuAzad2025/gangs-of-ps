from extensions import db
from datetime import datetime, timezone


class FarmSupplyContract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False, index=True)
    bonus_percent = db.Column(db.Float, default=0.1)
    status = db.Column(db.String(16), default='active', index=True)  # active | expired
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ends_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('farm_contracts', lazy=True))

    @property
    def is_active(self):
        if self.status != 'active':
            return False
        now = datetime.now(timezone.utc)
        ends = self.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        return bool(ends and ends > now)

