from datetime import datetime
from extensions import db


class GameRoom(db.Model):
    __tablename__ = 'game_rooms'

    id = db.Column(db.Integer, primary_key=True)
    game_type = db.Column(db.String(20), nullable=False)  # 'chess', 'trix'
    name = db.Column(db.String(64), nullable=False)
    # 'waiting', 'playing', 'finished'
    status = db.Column(db.String(20), default='waiting')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # JSON field to store game state (board FEN, cards, turn, etc.)
    game_state = db.Column(db.JSON, default={})

    # Betting Logic
    currency_type = db.Column(db.String(20),
                              default='money')  # 'money' or 'diamonds'
    stake_amount = db.Column(db.BigInteger, default=0)
    pot_amount = db.Column(db.BigInteger, default=0)

    # Relationships
    players = db.relationship(
        'GamePlayer',
        backref='room',
        lazy='dynamic',
        cascade='all, delete-orphan')
    messages = db.relationship(
        'GameChat',
        backref='room',
        lazy='dynamic',
        cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'game_type': self.game_type,
            'name': self.name,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'currency_type': self.currency_type,
            'stake_amount': self.stake_amount,
            'pot_amount': self.pot_amount,
            'players': [p.to_dict() for p in self.players],
            'game_state': self.game_state
        }


class GamePlayer(db.Model):
    __tablename__ = 'game_players'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('game_rooms.id'),
        nullable=False,
        index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 0 for White/Player1, 1 for Black/Player2, etc.
    seat_index = db.Column(db.Integer)
    is_ready = db.Column(db.Boolean, default=False)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'avatar': self.user.avatar if self.user else 'default.png',
            'seat_index': self.seat_index,
            'is_ready': self.is_ready
        }


class GameChat(db.Model):
    __tablename__ = 'game_chat'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(
        db.Integer,
        db.ForeignKey('game_rooms.id'),
        nullable=False,
        index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    message = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'avatar': self.user.avatar if self.user else 'default.png',
            'message': self.message,
            'created_at': self.created_at.strftime('%H:%M')
        }
