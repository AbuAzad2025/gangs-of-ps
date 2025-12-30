from extensions import db
from datetime import datetime, timezone


class FactoryJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    job_type = db.Column(db.String(32), nullable=False)  # bullets | explosives
    metal_used = db.Column(db.Integer, default=0)
    diamonds_used = db.Column(db.Integer, default=0)
    output_amount = db.Column(db.Integer, default=0)
    status = db.Column(db.String(16), default='running')  # running | claimed | canceled
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ends_at = db.Column(db.DateTime, nullable=False)
    claimed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('factory_jobs', lazy=True))

    @property
    def is_ready(self):
        now = datetime.now(timezone.utc)
        ends = self.ends_at
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        return bool(ends and ends <= now)

