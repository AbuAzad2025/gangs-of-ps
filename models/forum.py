from datetime import datetime, timezone
from extensions import db


class ForumCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)
    min_rank = db.Column(db.Integer, default=0)  # 0 for everyone
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    topics = db.relationship('ForumTopic', backref='category', lazy='dynamic')


class ForumTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey('forum_category.id'),
        nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    last_post_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    user = db.relationship('User', backref='topics')
    posts = db.relationship(
        'ForumPost',
        backref='topic',
        lazy='dynamic',
        cascade='all, delete-orphan')


class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey('forum_topic.id'),
        nullable=False,
        index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        onupdate=lambda: datetime.now(
            timezone.utc))

    user = db.relationship('User', backref='posts')
