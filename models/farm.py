from extensions import db
from datetime import datetime, timezone


class FarmJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    farm_type = db.Column(db.String(32), nullable=False)  # olive | zaatar | soap | dates | keffiyeh | pottery
    output_item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True, index=True)
    output_amount = db.Column(db.Integer, default=0)
    diamonds_used = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default='running')  # running | claimed | canceled
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ends_at = db.Column(db.DateTime, nullable=False)
    claimed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('farm_jobs', lazy=True))
    output_item = db.relationship('Item')

    @property
    def is_ready(self):
        now = datetime.now(timezone.utc)
        ends = self.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        return bool(ends and ends <= now)

