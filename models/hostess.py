from extensions import db
from datetime import datetime, timezone

class Hostess(db.Model):
    __tablename__ = 'hostesses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(32), nullable=False) # luck, spy, support
    price = db.Column(db.Integer, default=1000)
    image = db.Column(db.String(128), default='default_hostess.jpg')
    description = db.Column(db.Text)
    dialogue_style = db.Column(db.String(32), default='friendly') # friendly, mysterious, flirty, energetic
    intro_message = db.Column(db.String(256))
    
    # Buffs
    buff_type = db.Column(db.String(32)) # casino_luck, gym_boost, hospital_recovery, crime_success
    buff_value = db.Column(db.Float, default=0.0) # e.g., 0.10 for 10%
    
    # AI Training Data
    system_prompt = db.Column(db.Text) # Custom prompt for this specific hostess
    training_examples = db.Column(db.Text) # JSON string of few-shot examples [{"user": "...", "assistant": "..."}]
    
    # Video Configuration
    video = db.Column(db.String(128)) # Path to video file (mp4/webm)
    video_prompt = db.Column(db.Text) # JSON prompt for video generation (Sora/Runway style)

    # Voice & Personality Configuration
    voice_config = db.Column(db.Text) # JSON: {"provider": "browser|elevenlabs", "voice_id": "...", "pitch": 1.0, "rate": 1.0}
    personality_config = db.Column(db.Text) # JSON: {"flirt_level": 1-10, "shyness": 1-10, "dominance": 1-10}
    appearance_config = db.Column(db.Text) # JSON: {"clothing": "...", "hair": "...", "body": "...", "accessories": "..."}
    knowledge_base = db.Column(db.Text) # User manual or specific knowledge for the hostess
    is_avatar_active = db.Column(db.Boolean, default=False) # Enable "Real Human Avatar" mode (video loop)
    self_learning_enabled = db.Column(db.Boolean, default=True)
    memory_enabled = db.Column(db.Boolean, default=True)
    last_trained_at = db.Column(db.DateTime, nullable=True)

    is_active = db.Column(db.Boolean, default=True)

    # RPG Stats
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.Integer, default=0)
    charm = db.Column(db.Integer, default=10) # Increases buff effectiveness
    intelligence = db.Column(db.Integer, default=10) # Unlocks more knowledge
    combat_skill = db.Column(db.Integer, default=0) # For combat support
    loyalty = db.Column(db.Integer, default=50) # Affects willingness to do risky tasks
    
    special_move_cooldown = db.Column(db.DateTime, nullable=True)

    # Exclusivity & Ranking
    current_player_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, unique=True)
    min_rank = db.Column(db.Integer, default=1) # Minimum level required
    is_public = db.Column(db.Boolean, default=False) # If True (e.g. Jasmin), she is not hireable/exclusive

    # Relationship
    current_player = db.relationship('User', foreign_keys=[current_player_id], backref=db.backref('hired_hostess', uselist=False))

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

class VideoScenario(db.Model):
    __tablename__ = 'video_scenarios'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    script_json = db.Column(db.Text, nullable=False) # The full JSON content
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
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
    hostess_id = db.Column(db.Integer, db.ForeignKey('hostesses.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class HostessMemory(db.Model):
    __tablename__ = 'hostess_memories'

    id = db.Column(db.Integer, primary_key=True)
    hostess_id = db.Column(db.Integer, db.ForeignKey('hostesses.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    key = db.Column(db.String(64), nullable=False, index=True)
    value = db.Column(db.Text, nullable=False)
    importance = db.Column(db.Integer, default=1)
    source = db.Column(db.String(16), default='auto')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
