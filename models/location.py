from extensions import db
from sqlalchemy import event
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))
    cost = db.Column(db.Integer, default=100)
    cooldown = db.Column(db.Integer, default=300)  # seconds
    image = db.Column(db.String(100), default='default_city.jpg')
    # e.g., 'commerce', 'defense', 'health'
    specialty = db.Column(db.String(50))
    specialty_value = db.Column(db.Integer,
                                default=0)  # Percentage or flat value

    def __repr__(self):
        return f'<Location {self.name}>'


class LocationControl(db.Model):
    __tablename__ = 'location_control'

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(
        db.Integer,
        db.ForeignKey('location.id'),
        nullable=False,
        index=True)
    gang_id = db.Column(
        db.Integer,
        db.ForeignKey('gang.id'),
        nullable=False,
        index=True)
    week_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)

    __table_args__ = (
        UniqueConstraint(
            'location_id',
            'gang_id',
            'week_number',
            'year',
            name='uq_location_control_loc_gang_week_year'),
    )

    location = db.relationship('Location', foreign_keys=[location_id])
    gang = db.relationship('Gang', foreign_keys=[gang_id])

    def __repr__(self):
        return f'<LocationControl loc={self.location_id} gang={self.gang_id} week={self.week_number}/{self.year}>'


@event.listens_for(Location.__table__, 'after_create')
def _seed_default_location(target, connection, **kw):
    connection.execute(target.insert().values(name='Default City'))
