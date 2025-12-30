from extensions import db
from datetime import datetime, timezone
from flask_babel import _
from sqlalchemy.dialects.postgresql import JSON

class Crime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    energy_cost = db.Column(db.Integer, default=10)
    money_reward_min = db.Column(db.Integer, default=10)
    money_reward_max = db.Column(db.Integer, default=100)
    exp_reward = db.Column(db.Integer, default=10)
    min_level = db.Column(db.Integer, default=1)
    cooldown = db.Column(db.Integer, default=60) # Seconds
    image = db.Column(db.String(100), default='default_crime.jpg')
    is_active = db.Column(db.Boolean, default=True)
    
    # Reward configuration
    reward_type = db.Column(db.String(20), default='money')  # money, vehicle, item
    reward_item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    reward_item = db.relationship('Item', foreign_keys=[reward_item_id])
    
    # Stat Requirements
    min_strength = db.Column(db.Integer, default=0)
    min_agility = db.Column(db.Integer, default=0)
    min_intelligence = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Crime {self.name}>'

class OrganizedCrime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    min_level = db.Column(db.Integer, default=10)
    min_members = db.Column(db.Integer, default=2)
    max_members = db.Column(db.Integer, default=4)
    duration_minutes = db.Column(db.Integer, default=60)
    cooldown_hours = db.Column(db.Integer, default=24)
    energy_cost = db.Column(db.Integer, default=50)
    is_active = db.Column(db.Boolean, default=True)
    
    # Rewards (Total pool to be split)
    money_reward_min = db.Column(db.Integer, default=1000)
    money_reward_max = db.Column(db.Integer, default=5000)
    exp_reward = db.Column(db.Integer, default=100)
    
    # Requirements (JSON: {"driver": {"agility": 20}, "muscle": {"strength": 20}})
    requirements = db.Column(db.Text, default="{}") 
    
    image = db.Column(db.String(100), default='default_heist.jpg')
    roles_config = db.Column(JSON, default=list)
    min_gang_level = db.Column(db.Integer, default=1)
    
    def __repr__(self):
        return f'<OrganizedCrime {self.name}>'

class CrimeLobby(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crime_id = db.Column(db.Integer, db.ForeignKey('organized_crime.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='open', index=True) # open, full, in_progress, completed, failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    
    crime = db.relationship('OrganizedCrime')
    leader = db.relationship('User', foreign_keys=[leader_id])
    participants = db.relationship('LobbyParticipant', backref='lobby', lazy=True, cascade='all, delete-orphan')

class LobbyParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lobby_id = db.Column(db.Integer, db.ForeignKey('crime_lobby.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    role_name = db.Column(db.String(50)) # driver, muscle, hacker, etc.
    is_ready = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User')

class HeistHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crime_name = db.Column(db.String(100))
    leader_name = db.Column(db.String(64))
    participants_snapshot = db.Column(JSON, default=list) # Full snapshot of participants and rewards
    success = db.Column(db.Boolean, default=False)
    money_earned = db.Column(db.Integer, default=0)
    exp_earned = db.Column(db.Integer, default=0)
    log_details = db.Column(db.Text) # The story of what happened
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<HeistHistory {self.crime_name} - {self.created_at}>'

class DailyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    target_type = db.Column(db.String(50), nullable=False) # crime, gym, combat, buy
    target_count = db.Column(db.Integer, default=1)
    reward_money = db.Column(db.Integer, default=0)
    reward_exp = db.Column(db.Integer, default=0)
    min_level = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<DailyTask {self.description}>'

class UserDailyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('daily_task.id'), nullable=False)
    progress = db.Column(db.Integer, default=0)
    is_completed = db.Column(db.Boolean, default=False)
    date = db.Column(db.Date, default=lambda: datetime.now(timezone.utc).date())
    
    task = db.relationship('DailyTask')
    user = db.relationship('User', backref=db.backref('daily_tasks', lazy=True))

    @property
    def title(self):
        # Generate a title based on target_type
        type_titles = {
            'crime': _('إجرام'),
            'gym': _('تمرين'),
            'combat': _('قتال'),
            'buy': _('تسوق')
        }
        return type_titles.get(self.task.target_type, self.task.target_type.title())

    @property
    def description(self):
        return self.task.description

    @property
    def goal(self):
        return self.task.target_count

    @property
    def reward(self):
        rewards = []
        if self.task.reward_money > 0:
            rewards.append(f"{self.task.reward_money} {_('شيكل')}")
        if self.task.reward_exp > 0:
            rewards.append(f"{self.task.reward_exp} {_('خبرة')}")
        return " + ".join(rewards)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rank_points = db.Column(db.Integer, default=0)
    
    user = db.relationship('User', backref=db.backref('progress', uselist=False))

class ResurrectionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admin_note = db.Column(db.String(255))
    
    user = db.relationship('User', backref=db.backref('resurrection_requests', lazy=True, cascade='all, delete-orphan'))

class UserCrimeCooldown(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    crime_id = db.Column(db.Integer, db.ForeignKey('crime.id'), nullable=False)
    cooldown_until = db.Column(db.DateTime, nullable=False)
    
    user = db.relationship('User', backref=db.backref('crime_cooldowns', lazy=True, cascade='all, delete-orphan'))
    crime = db.relationship('Crime')

class InvestigationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investigator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    success = db.Column(db.Boolean, default=False)
    details = db.Column(db.Text, nullable=True) # JSON string or plain text report
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    investigator = db.relationship('User', foreign_keys=[investigator_id], backref='investigations_made')
    target = db.relationship('User', foreign_keys=[target_id], backref='investigations_received')
