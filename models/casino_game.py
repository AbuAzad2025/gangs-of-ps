from extensions import db
from datetime import datetime, timezone


class CasinoGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    # 'blackjack', 'slots', 'roulette'
    game_type = db.Column(db.String(32), nullable=False)
    bet_amount = db.Column(db.BigInteger, nullable=False)
    state = db.Column(db.JSON, nullable=True)  # Deck, Hand, etc.
    status = db.Column(
        db.String(20),
        default='active',
        index=True)  # 'active', 'completed'
    result = db.Column(db.String(20), nullable=True)  # 'win', 'loss', 'push'
    winnings = db.Column(db.BigInteger, default=0)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(
            timezone.utc), onupdate=lambda: datetime.now(
            timezone.utc))

    user = db.relationship(
        'User', backref=db.backref(
            'casino_games', lazy='dynamic'))
