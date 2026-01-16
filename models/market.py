from extensions import db
from datetime import datetime, timezone


class MarketAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(
        db.String(10),
        unique=True,
        nullable=False)  # e.g., AAPL, BTC-USD
    name = db.Column(db.String(100), nullable=False)
    asset_type = db.Column(
        db.String(20),
        default='stock',
        index=True)  # stock, crypto
    current_price = db.Column(db.Float, default=0.0)
    price_change_24h = db.Column(db.Float, default=0.0)  # Percentage change
    high_24h = db.Column(db.Float, default=0.0)
    low_24h = db.Column(db.Float, default=0.0)
    volume_24h = db.Column(db.Float, default=0.0)
    last_updated = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    @property
    def image_path(self):
        # Return relative path for use with url_for('static', filename=...)
        # You can map symbols to specific images here
        if self.asset_type == 'crypto':
            return 'images/items/default.jpg'  # Placeholder for crypto
        return 'images/items/default.jpg'  # Placeholder for stocks

    def __repr__(self):
        return f'<MarketAsset {self.symbol}>'


class UserInvestment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey('market_asset.id'),
        nullable=False,
        index=True)
    quantity = db.Column(db.Float, default=0.0)
    average_buy_price = db.Column(db.Float, default=0.0)

    # Relationships
    asset = db.relationship('MarketAsset', backref='investments')
    user = db.relationship('User', backref='investments')

    __table_args__ = (
        db.Index(
            'idx_user_investment_user_asset',
            'user_id',
            'asset_id',
            unique=True),
    )

    def current_value(self):
        return self.quantity * self.asset.current_price

    def profit_loss(self):
        invested = self.quantity * self.average_buy_price
        current = self.current_value()
        return current - invested


class FuturesPosition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey('market_asset.id'),
        nullable=False,
        index=True)

    position_type = db.Column(
        db.String(10),
        nullable=False,
        index=True)  # 'long' or 'short'
    entry_price = db.Column(db.Float, nullable=False)
    margin_amount = db.Column(db.Float, nullable=False)  # Cash locked
    leverage = db.Column(db.Integer, default=1)
    # Total size (Margin * Leverage / Entry)
    quantity = db.Column(db.Float, nullable=False)

    liquidation_price = db.Column(db.Float, nullable=False, index=True)
    is_open = db.Column(db.Boolean, default=True, index=True)
    opened_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)
    closed_at = db.Column(db.DateTime, nullable=True, index=True)

    # Relationships
    asset = db.relationship('MarketAsset', backref='futures_positions')
    user = db.relationship('User', backref='futures_positions')

    __table_args__ = (
        db.Index(
            'idx_futures_position_user_open',
            'user_id',
            'is_open'),
        db.Index(
            'idx_futures_liq_check',
            'asset_id',
            'is_open',
            'position_type',
            'liquidation_price'),
    )

    def calculate_pnl(self):
        current_price = self.asset.current_price
        if self.position_type == 'long':
            # Value difference * Quantity
            diff = current_price - self.entry_price
            return diff * self.quantity
        else:  # short
            diff = self.entry_price - current_price
            return diff * self.quantity

    def calculate_roi(self):
        pnl = self.calculate_pnl()
        if self.margin_amount > 0:
            return (pnl / self.margin_amount) * 100
        return 0.0


class SpotOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey('market_asset.id'),
        nullable=False)

    order_type = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    price = db.Column(db.Float, nullable=False)  # Limit Price
    quantity = db.Column(db.Float, nullable=False)
    filled_quantity = db.Column(db.Float, default=0.0)

    # open, filled, cancelled, partial
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)

    # Relationships
    asset = db.relationship('MarketAsset', backref='spot_orders')
    user = db.relationship('User', backref='spot_orders')

    __table_args__ = (
        db.Index('idx_spot_order_asset_status', 'asset_id', 'status'),
        db.Index('idx_spot_order_user_status', 'user_id', 'status'),
        db.Index('idx_spot_order_exec_buy', 'asset_id', 'status', 'order_type', 'price'),
    )

    def progress_percent(self):
        if self.quantity > 0:
            return (self.filled_quantity / self.quantity) * 100
        return 0.0


class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # 'item', 'title', 'vehicle', 'special'
    item_type = db.Column(db.String(20), nullable=False)
    item_id = db.Column(db.String(50), nullable=True)  # ID or Key of the item
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        index=True)  # Null = System Auction

    start_price = db.Column(db.BigInteger, nullable=False)
    current_price = db.Column(db.BigInteger, nullable=False)
    min_bid_increment = db.Column(db.BigInteger, default=1000)

    start_time = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(
        db.String(20),
        default='active',
        index=True)  # active, completed, cancelled

    winner_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        index=True)

    # Relationships
    seller = db.relationship(
        'User',
        foreign_keys=[seller_id],
        backref='auctions_sold')
    winner = db.relationship(
        'User',
        foreign_keys=[winner_id],
        backref='auctions_won')
    bids = db.relationship(
        'AuctionBid',
        backref='auction',
        lazy=True,
        cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Auction {self.id} - {self.item_type}:{self.item_id}>'

    @property
    def is_active(self):
        end_time_aware = self.end_time
        if end_time_aware.tzinfo is None:
            end_time_aware = end_time_aware.replace(tzinfo=timezone.utc)
        return self.status == 'active' and end_time_aware > datetime.now(
            timezone.utc)


class AuctionBid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(
        db.Integer,
        db.ForeignKey('auction.id'),
        nullable=False,
        index=True)
    bidder_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    amount = db.Column(db.BigInteger, nullable=False)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)
    is_refunded = db.Column(db.Boolean, default=False)

    bidder = db.relationship('User', backref='auction_bids')

    def __repr__(self):
        return f'<Bid {self.amount} on Auction {self.auction_id}>'
