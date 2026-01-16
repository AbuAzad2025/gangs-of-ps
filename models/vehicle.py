from extensions import db


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Types: 'legal_il' (Yellow Plate), 'legal_pal' (White/Green Plate),
    # 'mushtuba' (No Plate/Illegal)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    price = db.Column(db.Integer, nullable=False)
    speed = db.Column(db.Integer, default=10)  # Affects travel/escape
    defense = db.Column(db.Integer, default=10)  # Protection from attacks
    # 0-100% chance of seizure by police
    risk = db.Column(db.Integer, default=0)
    image = db.Column(db.String(100))  # Path to image
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Vehicle {self.name} ({self.type})>'


class UserVehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey('vehicle.id'),
        nullable=False,
        index=True)
    is_active = db.Column(db.Boolean, default=False)
    condition = db.Column(db.Integer, default=100)  # 0-100%
    # Upgrades
    engine_level = db.Column(db.Integer, default=0)
    tires_level = db.Column(db.Integer, default=0)
    armor_level = db.Column(db.Integer, default=0)

    repair_until = db.Column(db.DateTime, nullable=True)

    vehicle = db.relationship('Vehicle')
    user = db.relationship('User', backref=db.backref('garage', lazy=True))
