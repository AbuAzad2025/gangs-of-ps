from extensions import db
from datetime import datetime, timezone


class UserFacility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    facility_key = db.Column(db.String(32), nullable=False, index=True)
    level = db.Column(db.Integer, default=0)
    last_perk_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    user = db.relationship(
        'User',
        backref=db.backref(
            'facilities',
            lazy=True,
            cascade='all, delete-orphan'))
