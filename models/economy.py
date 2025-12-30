from extensions import db
from datetime import datetime, timedelta, timezone
from sqlalchemy import event

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # house, car, business
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    gang_id = db.Column(db.Integer, db.ForeignKey('gang.id'), nullable=True)
    value = db.Column(db.Integer, default=0) # Buying Price
    income = db.Column(db.Integer, default=0) # Daily income or benefit
    last_collected = db.Column(db.DateTime, nullable=True)
    image = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    
    @property
    def can_collect(self):
        if not self.last_collected:
            return True
        last = self.last_collected
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        else:
            last = last.astimezone(timezone.utc)
        return datetime.now(timezone.utc) >= last + timedelta(hours=24)

    @property
    def next_collection_time(self):
        if not self.last_collected:
            return datetime.now(timezone.utc)
        last = self.last_collected
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        else:
            last = last.astimezone(timezone.utc)
        return last + timedelta(hours=24)

    def __repr__(self):
        return f'<Asset {self.name}>'

def _normalize_utc_naive(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

@event.listens_for(Asset, 'before_insert')
def _asset_before_insert(mapper, connection, target):
    target.last_collected = _normalize_utc_naive(target.last_collected)

@event.listens_for(Asset, 'before_update')
def _asset_before_update(mapper, connection, target):
    target.last_collected = _normalize_utc_naive(target.last_collected)
