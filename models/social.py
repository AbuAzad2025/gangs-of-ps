from extensions import db
from datetime import datetime, timezone

class Gang(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    
    # Hierarchy
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True, name='fk_gang_leader_id'), nullable=False, index=True)
    underboss_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True, name='fk_gang_underboss_id'), nullable=True)
    
    # Stats
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.Integer, default=0)
    money = db.Column(db.Integer, default=0) # Gang Vault
    bullets = db.Column(db.Integer, default=0) # Gang Armory
    max_members = db.Column(db.Integer, default=5) # Max capacity
    
    # Policies
    min_level_req = db.Column(db.Integer, default=1)
    recruitment_status = db.Column(db.String(20), default='open') # open, invite_only, closed
    allowed_countries = db.Column(db.String(255), nullable=True) # Comma separated ISO codes

    last_organized_crime_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    members = db.relationship('User', backref='gang', lazy=True, foreign_keys='User.gang_id')
    leader = db.relationship('User', foreign_keys=[leader_id], backref='leader_of_gang')
    invites = db.relationship('GangInvite', backref='gang', lazy=True, cascade='all, delete-orphan')
    logs = db.relationship('GangLog', backref='gang', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Gang {self.name}>'

class GangInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gang_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending') # pending, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class GangLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gang_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Who performed the action
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id], backref='gang_logs')


class GangWar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gang1_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False)
    gang2_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False)
    
    score_gang1 = db.Column(db.Integer, default=0)
    score_gang2 = db.Column(db.Integer, default=0)
    
    start_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = db.Column(db.DateTime, nullable=True)
    
    status = db.Column(db.String(20), default='active') # active, ended
    war_type = db.Column(db.String(50), default='street') # street, cyber, economic
    winner_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=True)

    gang1 = db.relationship('Gang', foreign_keys=[gang1_id], backref='wars_started')
    gang2 = db.relationship('Gang', foreign_keys=[gang2_id], backref='wars_received')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    deleted_by_sender = db.Column(db.Boolean, default=False)
    deleted_by_receiver = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivery_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc)) # For delayed messages
    
    def __repr__(self):
        return f'<Message {self.subject}>'

class GangAlliance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    gang1_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False)
    gang2_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, active
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    gang1 = db.relationship('Gang', foreign_keys=[gang1_id], backref='alliances_initiated')
    gang2 = db.relationship('Gang', foreign_keys=[gang2_id], backref='alliances_received')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    type = db.Column(db.String(50), default='info') # info, success, warning, danger
    link = db.Column(db.String(255), nullable=True) # Optional link to redirect to
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))

    def __repr__(self):
        return f'<Notification {self.title}>'
