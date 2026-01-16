from extensions import db


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    # weapon, armor, consumable
    type = db.Column(db.String(50), nullable=False)
    cost = db.Column(db.Integer, default=0)
    is_black_market = db.Column(db.Boolean, default=False)
    image = db.Column(db.String(255))

    # Stats bonuses
    bonus_strength = db.Column(db.Integer, default=0)
    bonus_defense = db.Column(db.Integer, default=0)
    bonus_agility = db.Column(db.Integer, default=0)

    # Combat
    ammo_needed = db.Column(db.Integer, default=0)  # Bullets per attack

    # Recovery
    recover_energy = db.Column(db.Integer, default=0)
    recover_health = db.Column(db.Integer, default=0)
    recover_brave = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Item {self.name}>'


class UserItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    item_id = db.Column(
        db.Integer,
        db.ForeignKey('item.id'),
        nullable=False,
        index=True)
    quantity = db.Column(db.Integer, default=1)
    is_equipped = db.Column(db.Boolean, default=False)
    condition = db.Column(db.Integer, default=100)

    item = db.relationship('Item')
    user = db.relationship(
        'User', backref=db.backref(
            'inventory', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_user_item_user_equipped', 'user_id', 'is_equipped'),
    )
