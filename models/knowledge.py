from extensions import db
from datetime import datetime


class HostessKnowledge(db.Model):
    __tablename__ = 'hostess_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    hostess_id = db.Column(
        db.Integer,
        db.ForeignKey('hostesses.id'),
        nullable=True,
        index=True)  # Link to specific hostess, null means general knowledge
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    # e.g., company, gameplay, technical, general
    category = db.Column(db.String(64), index=True)
    # Comma-separated keywords for simpler search
    keywords = db.Column(db.Text)
    language = db.Column(
        db.String(10),
        default='ar',
        index=True)  # 'ar' or 'en'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'hostess_id': self.hostess_id,
            'question': self.question,
            'answer': self.answer,
            'category': self.category,
            'keywords': self.keywords,
            'language': self.language
        }


class LearningLog(db.Model):
    __tablename__ = 'learning_logs'

    id = db.Column(db.Integer, primary_key=True)
    # Removed ForeignKey constraint to avoid circular dependency issues during
    # seed
    user_id = db.Column(db.Integer, nullable=True)
    user_question = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)
    # True/False if user gives feedback
    was_helpful = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'question': self.user_question,
            'response': self.ai_response,
            'created_at': self.created_at
        }
