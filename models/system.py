from extensions import db
from datetime import datetime, timezone


class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))

    @staticmethod
    def get_value(key, default=None):
        try:
            config = SystemConfig.query.filter_by(key=key).first()
            return config.value if config else default
        except Exception:
            db.session.rollback()
            return default

    @staticmethod
    def set_value(key, value, description=None):
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        config.value = str(value)
        if description:
            config.description = description
        db.session.commit()


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    def __repr__(self):
        return f'<Announcement {self.title}>'


class SecurityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # e.g., 'master_key_success', 'master_key_fail', 'brute_force'
    event_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50))
    details = db.Column(db.Text)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    def __repr__(self):
        return f'<SecurityLog {self.event_type} at {self.timestamp}>'
