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

class ConfigLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    reason = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    admin = db.relationship('User', backref='config_logs')

    def __repr__(self):
        return f'<ConfigLog {self.key} by {self.admin_id}>'

class UserLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True) # CRIME, TRANSFER, LOGIN, etc.
    details = db.Column(db.Text, nullable=True) # JSON or text details
    result = db.Column(db.String(20), default='success') # success, fail
    before_state = db.Column(db.JSON, nullable=True) # Snapshot before
    after_state = db.Column(db.JSON, nullable=True) # Snapshot after
    ip_address = db.Column(db.String(45), nullable=True) # IPv6 is max 45 chars
    user_agent = db.Column(db.String(255), nullable=True) # Browser/Device info
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    user = db.relationship('User', backref='user_logs')

    def __repr__(self):
        return f'<UserLog {self.action} by {self.user_id}>'

class EconomySnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date(), index=True)
    total_money = db.Column(db.BigInteger, default=0)
    total_bank = db.Column(db.BigInteger, default=0)
    avg_wealth = db.Column(db.BigInteger, default=0)
    top_1_percent_share = db.Column(db.Float, default=0.0) # Percentage of total wealth held by top 1%
    active_users_24h = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<EconomySnapshot {self.date}>'

class MoneySinkLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    sink_type = db.Column(db.String(50), nullable=False) # bank_fee, property_maintenance, repair, upgrade, etc.
    amount = db.Column(db.Integer, nullable=False)
    details = db.Column(db.String(255)) # e.g., "Tier 2 Fee", "Villa Maintenance"
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship('User', backref='sink_logs')

    def __repr__(self):
        return f'<MoneySinkLog {self.sink_type} - {self.amount}>'
