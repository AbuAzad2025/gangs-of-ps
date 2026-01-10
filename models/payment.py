from extensions import db
from datetime import datetime, timezone

class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    user = db.relationship('User', backref='transactions')
    amount_usd = db.Column(db.Float, nullable=False)
    diamonds_amount = db.Column(db.Integer, nullable=False)
    transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, completed, rejected
    payment_method = db.Column(db.String(50)) # bank, wallet, contact
    payment_proof = db.Column(db.Text) # User submitted details
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Transaction {self.transaction_id} - {self.status}>'
