from extensions import db
from datetime import datetime, timezone


class Hostess(db.Model):
    __tablename__ = 'hostesses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False)  # luck, spy, support
    price = db.Column(db.Integer, default=1000)
    image = db.Column(db.String(128), default='default_hostess.jpg')
    description = db.Column(db.Text)
    # friendly, mysterious, flirty, energetic
    dialogue_style = db.Column(db.String(32), default='friendly')
    intro_message = db.Column(db.String(256))

    # Buffs
    # casino_luck, gym_boost, hospital_recovery, crime_success
    buff_type = db.Column(db.String(32))
    buff_value = db.Column(db.Float, default=0.0)  # e.g., 0.10 for 10%

    # AI Training Data
    # Custom prompt for this specific hostess
    system_prompt = db.Column(db.Text)
    # JSON string of few-shot examples [{"user": "...", "assistant": "..."}]
    training_examples = db.Column(db.Text)

    # Video Configuration
    video = db.Column(db.String(128))  # Path to video file (mp4/webm)
    # JSON prompt for video generation (Sora/Runway style)
    video_prompt = db.Column(db.Text)

    # Voice & Personality Configuration
    # JSON: {"provider": "browser|elevenlabs", "voice_id": "...", "pitch": 1.0, "rate": 1.0}
    voice_config = db.Column(db.Text)
    # JSON: {"flirt_level": 1-10, "shyness": 1-10, "dominance": 1-10}
    personality_config = db.Column(db.Text)
    # JSON: {"clothing": "...", "hair": "...", "body": "...", "accessories": "..."}
    appearance_config = db.Column(db.Text)
    # User manual or specific knowledge for the hostess
    knowledge_base = db.Column(db.Text)
    # Enable "Real Human Avatar" mode (video loop)
    is_avatar_active = db.Column(db.Boolean, default=False)
    self_learning_enabled = db.Column(db.Boolean, default=True)
    memory_enabled = db.Column(db.Boolean, default=True)
    last_trained_at = db.Column(db.DateTime, nullable=True)

    is_active = db.Column(db.Boolean, default=True)

    # RPG Stats
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.Integer, default=0)
    charm = db.Column(db.Integer, default=10)  # Increases buff effectiveness
    intelligence = db.Column(db.Integer, default=10)  # Unlocks more knowledge
    combat_skill = db.Column(db.Integer, default=0)  # For combat support
    # Affects willingness to do risky tasks
    loyalty = db.Column(db.Integer, default=50)

    special_move_cooldown = db.Column(db.DateTime, nullable=True)

    # Exclusivity & Ranking
    current_player_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'user.id',
            use_alter=True,
            name='fk_hostess_current_player_id'),
        nullable=True,
        unique=True)
    min_rank = db.Column(db.Integer, default=1)  # Minimum level required
    # If True (e.g. Jasmin), she is not hireable/exclusive
    is_public = db.Column(db.Boolean, default=False)

    # Relationship
    current_player = db.relationship(
        'User',
        foreign_keys=[current_player_id],
        backref=db.backref(
            'hired_hostess',
            uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'price': self.price,
            'image': self.image,
            'video': self.video,
            'description': self.description,
            'dialogue_style': self.dialogue_style,
            'intro': self.intro_message,
            'system_prompt': self.system_prompt,
            'training_examples': self.training_examples,
            'voice_config': self.voice_config,
            'personality_config': self.personality_config,
            'appearance_config': self.appearance_config,
            'knowledge_base': self.knowledge_base,
            'self_learning_enabled': self.self_learning_enabled,
            'memory_enabled': self.memory_enabled,
            'is_public': self.is_public,
            'min_rank': self.min_rank,
            'is_hired': self.current_player_id is not None
        }

    @property
    def image_path(self):
        img = (self.image or '').strip()
        name = (self.name or '').strip()
        name_l = name.lower()

        if img and ('/' in img) and (not img.endswith('default_hostess.jpg')):
            return img

        filename = img.split('/')[-1] if img else 'default_hostess.jpg'

        if filename == 'default_hostess.jpg':
            if ('ياسمين' in name) or ('jasmin' in name_l):
                filename = 'jasmin.jpg'
            elif ('سارة' in name) or ('sarah' in name_l) or ('sara' in name_l):
                filename = 'sarah.jpg'
            elif ('ليلى' in name) or ('layla' in name_l):
                filename = 'layla.jpg'
            elif ('روبي' in name) or ('ruby' in name_l):
                filename = 'ruby.webp'

        return f'hostesses/{filename}'


class VideoScenario(db.Model):
    __tablename__ = 'video_scenarios'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    script_json = db.Column(db.Text, nullable=False)  # The full JSON content
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'script_json': self.script_json
        }


class HostessChatMessage(db.Model):
    __tablename__ = 'hostess_chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    hostess_id = db.Column(
        db.Integer,
        db.ForeignKey('hostesses.id'),
        nullable=False,
        index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        index=True)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))


class HostessMemory(db.Model):
    __tablename__ = 'hostess_memories'

    id = db.Column(db.Integer, primary_key=True)
    hostess_id = db.Column(
        db.Integer,
        db.ForeignKey('hostesses.id'),
        nullable=False,
        index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
        index=True)
    key = db.Column(db.String(64), nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    importance = db.Column(db.Integer, default=1)
    source = db.Column(db.String(16), default='auto')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
