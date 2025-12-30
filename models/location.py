from extensions import db
from sqlalchemy import event

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))
    cost = db.Column(db.Integer, default=100)
    cooldown = db.Column(db.Integer, default=300) # seconds
    image = db.Column(db.String(100), default='default_city.jpg')
    specialty = db.Column(db.String(50)) # e.g., 'commerce', 'defense', 'health'
    specialty_value = db.Column(db.Integer, default=0) # Percentage or flat value

    def __repr__(self):
        return f'<Location {self.name}>'

@event.listens_for(Location.__table__, 'after_create')
def _seed_default_location(target, connection, **kw):
    connection.execute(target.insert().values(name='Default City'))
