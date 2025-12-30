from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum
from flask_babel import _
from flask import has_request_context, g
from datetime import datetime, timezone, timedelta
from sqlalchemy import UniqueConstraint, func, cast, select

class UserRole(Enum):
    GUEST = 0
    USER = 1
    SUBSCRIBER = 2
    MODERATOR = 3
    ADMIN = 4
    SUPER_ADMIN = 5
    DEVELOPER = 6

class UserRank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    min_level = db.Column(db.Integer, default=1, unique=True)
    resurrection_cost = db.Column(db.Float, default=10.0)
    
    def __repr__(self):
        return f'<Rank {self.name}>'

class EliteTitleSeat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title_key = db.Column(db.String(32), nullable=False, index=True)
    seat_index = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, unique=True, index=True)
    reserved_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint('title_key', 'seat_index', name='uq_elite_title_seat_title_index'),
    )


def _elite_config_int(key, default):
    from models.system import SystemConfig
    try:
        return int(SystemConfig.get_value(key, str(default)) or default)
    except Exception:
        return int(default)

def _elite_now(now=None):
    if now is not None:
        if getattr(now, "tzinfo", None) is None:
            return now.replace(tzinfo=timezone.utc)
        return now
    if has_request_context() and hasattr(g, "now_utc") and g.now_utc is not None:
        return g.now_utc
    return datetime.now(timezone.utc)


def _elite_now_naive(now=None):
    return _elite_now(now=now).replace(tzinfo=None)


def get_active_elite_seat(user_id, now=None):
    now_naive = _elite_now_naive(now=now)
    if has_request_context():
        cache = getattr(g, "_elite_seat_cache", None)
        if cache is None:
            cache = {}
            g._elite_seat_cache = cache
        if user_id in cache:
            seat = cache[user_id]
        else:
            seat = EliteTitleSeat.query.filter_by(user_id=user_id).first()
            cache[user_id] = seat
    else:
        seat = EliteTitleSeat.query.filter_by(user_id=user_id).first()
    if not seat:
        return None
    if seat.reserved_until and seat.reserved_until <= now_naive:
        return None
    return seat


def sync_elite_titles(now=None):
    from models.gameplay import UserProgress

    now = _elite_now(now=now)
    now_naive = now.replace(tzinfo=None)

    quotas = {
        "godfather": _elite_config_int("elite_quota_godfather", 5),
        "boss": _elite_config_int("elite_quota_boss", 15),
    }

    changed = False

    for title_key, quota in quotas.items():
        if quota <= 0:
            continue
        existing = EliteTitleSeat.query.filter_by(title_key=title_key).count()
        if existing < quota:
            for i in range(existing + 1, quota + 1):
                db.session.add(EliteTitleSeat(title_key=title_key, seat_index=i))
            changed = True

    expired = EliteTitleSeat.query.filter(
        EliteTitleSeat.reserved_until.isnot(None),
        EliteTitleSeat.reserved_until <= now_naive
    ).all()
    for seat in expired:
        seat.user_id = None
        seat.reserved_until = None
        changed = True

    def pick_candidate(title_key, min_effective_level):
        occupied_this = {
            uid
            for (uid,) in db.session.query(EliteTitleSeat.user_id).filter(
                EliteTitleSeat.title_key == title_key,
                EliteTitleSeat.user_id.isnot(None)
            ).all()
            if uid is not None
        }
        occupied_godfather = set()
        if title_key == "boss":
            occupied_godfather = {
                uid
                for (uid,) in db.session.query(EliteTitleSeat.user_id).filter(
                    EliteTitleSeat.title_key == "godfather",
                    EliteTitleSeat.user_id.isnot(None)
                ).all()
                if uid is not None
            }

        rows = db.session.query(
            User,
            func.coalesce(UserProgress.rank_points, 0).label("rp"),
        ).outerjoin(UserProgress, UserProgress.user_id == User.id).filter(
            User.health > 0
        ).order_by(
            User.level.desc(),
            func.coalesce(UserProgress.rank_points, 0).desc(),
            User.exp.desc(),
            User.id.asc(),
        ).limit(500).all()

        best = None
        best_key = None
        for user, rp in rows:
            if user.id in occupied_this:
                continue
            if title_key == "boss" and user.id in occupied_godfather:
                continue
            eff = int(user.level or 0) + (int(rp or 0) // 50)
            if eff < int(min_effective_level):
                continue
            key = (-eff, -int(user.level or 0), -int(rp or 0), -int(user.exp or 0), int(user.id))
            if best is None or key < best_key:
                best = user
                best_key = key

        return best

    def clear_user_seats(user_id):
        rows = EliteTitleSeat.query.filter_by(user_id=user_id).all()
        for r in rows:
            r.user_id = None
            r.reserved_until = None

    def fill_title(title_key, min_effective_level):
        nonlocal changed
        free = EliteTitleSeat.query.filter_by(title_key=title_key, user_id=None).order_by(EliteTitleSeat.seat_index.asc()).all()
        for seat in free:
            cand = pick_candidate(title_key, min_effective_level)
            if not cand:
                return
            clear_user_seats(cand.id)
            db.session.flush()
            seat.user_id = cand.id
            seat.reserved_until = None
            db.session.flush()
            changed = True

    if quotas.get("godfather", 0) > 0:
        fill_title("godfather", 100)
    if quotas.get("boss", 0) > 0:
        fill_title("boss", 80)

    if changed:
        db.session.commit()


def reserve_elite_titles_for_death(user_id, now=None):
    now = _elite_now(now=now)
    now_naive = now.replace(tzinfo=None)
    hours = _elite_config_int("elite_reservation_hours", 24)
    seat = EliteTitleSeat.query.filter_by(user_id=user_id).first()
    if not seat:
        try:
            sync_elite_titles(now=now)
        except Exception:
            pass
        seat = EliteTitleSeat.query.filter_by(user_id=user_id).first()
    if not seat:
        return None
    if seat.reserved_until and seat.reserved_until > now_naive:
        return seat
    seat.reserved_until = (now + timedelta(hours=hours)).replace(tzinfo=None)
    return seat


def clear_elite_title_reservation_on_resurrect(user_id, now=None):
    seat = get_active_elite_seat(user_id, now=now)
    if not seat:
        return None
    if seat.reserved_until is None:
        return seat
    seat.reserved_until = None
    return seat


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    
    # Profile
    avatar = db.Column(db.String(100), default='default.png')
    country = db.Column(db.String(2), default='PS') # ISO 2-letter code
    email = db.Column(db.String(120), unique=True, nullable=True) # Optional for now, required for verification
    is_verified = db.Column(db.Boolean, default=False)
    verified_on = db.Column(db.DateTime, nullable=True)
    
    # Game Stats
    level = db.Column(db.Integer, default=1)
    exp = db.Column(db.BigInteger, default=0)
    money = db.Column(db.BigInteger, default=100)
    bullets = db.Column(db.BigInteger, default=0)
    diamonds = db.Column(db.BigInteger, default=0)
    energy = db.Column(db.BigInteger, default=100)
    max_energy = db.Column(db.BigInteger, default=100)
    health = db.Column(db.Integer, default=100)
    max_health = db.Column(db.Integer, default=100)
    brave = db.Column(db.Integer, default=10) # For attacks
    max_brave = db.Column(db.Integer, default=10)
    
    # Combat Stats
    strength = db.Column(db.Integer, default=10)
    defense = db.Column(db.Integer, default=10)
    agility = db.Column(db.Integer, default=10)
    intelligence = db.Column(db.Integer, default=10)
    driving_skill = db.Column(db.Integer, default=1) # New stat for racing
    
    # Banking & Status
    bank_balance = db.Column(db.BigInteger, default=0)
    jail_until = db.Column(db.DateTime, nullable=True)
    hospital_until = db.Column(db.DateTime, nullable=True)
    gym_until = db.Column(db.DateTime, nullable=True)
    
    # Status Effects
    is_safe_house_active = db.Column(db.Boolean, default=False)
    safe_house_until = db.Column(db.DateTime, nullable=True)
    is_admin_protected = db.Column(db.Boolean, default=False)
    heat_points = db.Column(db.Integer, default=0)
    heat_updated_at = db.Column(db.DateTime, nullable=True)
    is_disguised = db.Column(db.Boolean, default=False)
    disguise_until = db.Column(db.DateTime, nullable=True)
    casino_luck_until = db.Column(db.DateTime, nullable=True)
    active_hostess_id = db.Column(db.Integer, nullable=True)

    # Admin/Moderation
    is_ghost_mode = db.Column(db.Boolean, default=False)
    banned_until = db.Column(db.DateTime, nullable=True)
    ban_reason = db.Column(db.String(255), nullable=True)

    # Social
    gang_id = db.Column(db.Integer, db.ForeignKey('gang.id', use_alter=True, name='fk_user_gang_id'), index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), default=1, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_daily_reward = db.Column(db.DateTime)
    daily_streak = db.Column(db.Integer, default=0)
    last_chase = db.Column(db.DateTime)
    crime_cooldown_until = db.Column(db.DateTime)
    organized_crime_cooldown_until = db.Column(db.DateTime)
    last_crime = db.Column(db.DateTime)
    last_travel = db.Column(db.DateTime)
    last_gym_training = db.Column(db.DateTime)
    last_attack = db.Column(db.DateTime)

    # Relationships
    location = db.relationship('Location', foreign_keys=[location_id])
    assets = db.relationship('Asset', backref='owner', lazy=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    unlocked_achievements = db.relationship('UserAchievement', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

    def apply_developer_power(self):
        if self.role != UserRole.DEVELOPER:
            return

        now = datetime.now(timezone.utc)
        self.is_verified = True
        self.verified_on = now

        self.level = max(self.level or 1, 100)
        self.exp = 0

        self.max_energy = max(self.max_energy or 100, 10000)
        self.max_health = max(self.max_health or 100, 10000)
        self.max_brave = max(self.max_brave or 10, 1000)
        self.energy = self.max_energy
        self.health = self.max_health
        self.brave = self.max_brave

        self.money = max(self.money or 0, 10_000_000_000)
        self.bullets = max(self.bullets or 0, 10_000_000)
        self.diamonds = max(self.diamonds or 0, 10_000_000)
        self.bank_balance = max(self.bank_balance or 0, 10_000_000_000)

        self.strength = max(self.strength or 0, 9999)
        self.defense = max(self.defense or 0, 9999)
        self.agility = max(self.agility or 0, 9999)
        self.intelligence = max(self.intelligence or 0, 9999)
        self.driving_skill = max(self.driving_skill or 1, 100)

        self.jail_until = None
        self.hospital_until = None
        self.gym_until = None
        self.crime_cooldown_until = None
        self.organized_crime_cooldown_until = None

        self.is_safe_house_active = True
        self.safe_house_until = (now + timedelta(days=3650)).replace(tzinfo=None)
        try:
            self.add_rank_points(1_000_000)
        except Exception:
            pass

    def _heat_now(self, now=None):
        if now is None:
            if has_request_context() and hasattr(g, "now_utc") and g.now_utc is not None:
                now = g.now_utc
            else:
                now = datetime.now(timezone.utc)
        if getattr(now, "tzinfo", None) is None:
            now = now.replace(tzinfo=timezone.utc)
        return now

    def heat_value(self, now=None):
        from models.system import SystemConfig

        now = self._heat_now(now=now)
        now_naive = now.replace(tzinfo=None)

        points = int(self.heat_points or 0)
        updated_at = self.heat_updated_at
        if not updated_at:
            return max(0, min(100, points))

        if getattr(updated_at, "tzinfo", None) is not None:
            updated_at = updated_at.replace(tzinfo=None)

        elapsed_minutes = int(max(0, (now_naive - updated_at).total_seconds()) // 60)
        try:
            decay_per_min = float(SystemConfig.get_value("heat_decay_per_minute", "0.10") or 0.10)
        except Exception:
            decay_per_min = 0.10

        decayed = int(points - (elapsed_minutes * decay_per_min))
        return max(0, min(100, decayed))

    def add_heat(self, amount, now=None):
        now = self._heat_now(now=now)
        now_naive = now.replace(tzinfo=None)

        current = self.heat_value(now=now)
        try:
            amount = int(amount)
        except Exception:
            amount = 0

        new_value = max(0, min(100, current + amount))
        self.heat_points = new_value
        self.heat_updated_at = now_naive if new_value > 0 else None
        return new_value

    def clear_heat(self):
        self.heat_points = 0
        self.heat_updated_at = None

    def unlock_achievement(self, key, title, description=None, points=0):
        from models.achievement import Achievement, UserAchievement

        achievement = Achievement.query.filter_by(key=key).first()
        if not achievement:
            achievement = Achievement(key=key, title=title, description=description, points=points)
            db.session.add(achievement)
            db.session.flush()

        existing = UserAchievement.query.filter_by(user_id=self.id, achievement_id=achievement.id).first()
        if existing:
            return existing

        ua = UserAchievement(user_id=self.id, achievement_id=achievement.id)
        db.session.add(ua)
        return ua

    @property
    def achievements(self):
        try:
            return [ua.achievement for ua in (self.unlocked_achievements or []) if ua.achievement]
        except Exception:
            return []

    @property
    def max_exp(self):
        return self.level * 100

    def check_level_up(self):
        leveled_up = False
        while self.exp >= self.max_exp:
            self.exp -= self.max_exp
            self.level += 1
            self.max_energy += 10
            self.max_health += 10
            self.max_brave += 1
            self.energy = self.max_energy
            self.health = self.max_health
            self.brave = self.max_brave
            
            # Bonus stats
            self.strength += 1
            self.defense += 1
            self.agility += 1
            self.intelligence += 1
            
            leveled_up = True
            
        return leveled_up
    
    def add_rank_points(self, points=0):
        if points and points > 0:
            try:
                from models.gameplay import UserProgress
                progress = UserProgress.query.filter_by(user_id=self.id).first()
                if progress:
                    progress.rank_points += points
                else:
                    progress = UserProgress(user_id=self.id, rank_points=points)
                    db.session.add(progress)
            except Exception:
                db.session.rollback()
    
    @property
    def rank_points_value(self):
        if has_request_context():
            cache = getattr(g, "_rank_points_cache", None)
            if cache is None:
                cache = {}
                g._rank_points_cache = cache
            if self.id in cache:
                return cache[self.id]
        try:
            from models.gameplay import UserProgress
            progress = UserProgress.query.filter_by(user_id=self.id).first()
            rp = progress.rank_points if progress else 0
            if has_request_context():
                g._rank_points_cache[self.id] = rp
            return rp
        except Exception:
            db.session.rollback()
            if has_request_context():
                g._rank_points_cache[self.id] = 0
            return 0
    
    @property
    def rank_progress_percent(self):
        rp = self.rank_points_value
        try:
            return int(((rp % 50) / 50) * 100)
        except:
            return 0

    @property
    def is_super_admin(self):
        return self.role in [UserRole.SUPER_ADMIN, UserRole.DEVELOPER]

    @property
    def is_admin(self):
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.DEVELOPER]

    @property
    def is_moderator(self):
        return self.role in [UserRole.MODERATOR, UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.DEVELOPER]
        
    @property
    def is_developer(self):
        return self.role == UserRole.DEVELOPER

    @property
    def rank_title(self):
        if has_request_context():
            cache = getattr(g, "_rank_title_cache", None)
            if cache is None:
                cache = {}
                g._rank_title_cache = cache
            if self.id in cache:
                return cache[self.id]
        # Try to find rank from DB
        try:
            from models.gameplay import UserProgress
            rp = 0
            try:
                progress = UserProgress.query.filter_by(user_id=self.id).first()
                if progress:
                    rp = progress.rank_points
            except Exception:
                db.session.rollback()
                rp = 0
            effective_level = self.level + (rp // 50)
            rank = UserRank.query.filter(UserRank.min_level <= effective_level).order_by(UserRank.min_level.desc()).first()
            if rank:
                elite_key = None
                try:
                    seat = get_active_elite_seat(self.id)
                    elite_key = seat.title_key if seat else None
                except Exception:
                    db.session.rollback()
                    elite_key = None

                if effective_level >= 100:
                    if elite_key == "godfather":
                        title = _('عراب')
                        if has_request_context():
                            g._rank_title_cache[self.id] = title
                        return title
                    if elite_key == "boss":
                        title = _('زعيم')
                        if has_request_context():
                            g._rank_title_cache[self.id] = title
                        return title
                    title = _('وكيل')
                    if has_request_context():
                        g._rank_title_cache[self.id] = title
                    return title
                if effective_level >= 80:
                    if elite_key == "boss":
                        title = _('زعيم')
                        if has_request_context():
                            g._rank_title_cache[self.id] = title
                        return title
                    title = _('وكيل')
                    if has_request_context():
                        g._rank_title_cache[self.id] = title
                    return title
                title = rank.name
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
        except:
            pass
            
        try:
            from models.gameplay import UserProgress
            rp = 0
            try:
                progress = UserProgress.query.filter_by(user_id=self.id).first()
                if progress:
                    rp = progress.rank_points
            except:
                rp = 0
            effective_level = self.level + (rp // 50)
        except:
            effective_level = self.level
        elite_key = None
        try:
            seat = get_active_elite_seat(self.id)
            elite_key = seat.title_key if seat else None
        except Exception:
            elite_key = None

        if effective_level >= 100:
            if elite_key == "godfather":
                title = _('عراب') # Godfather
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            if elite_key == "boss":
                title = _('زعيم') # Boss
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            title = _('وكيل') # Underboss
            if has_request_context():
                g._rank_title_cache[self.id] = title
            return title
        elif effective_level >= 80:
            if elite_key == "boss":
                title = _('زعيم') # Boss
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            title = _('وكيل') # Underboss
            if has_request_context():
                g._rank_title_cache[self.id] = title
            return title

        if effective_level < 3:
            title = _('متشرد') # Hobo
        elif effective_level < 5:
            title = _('نشال') # Pickpocket
        elif effective_level < 10:
            title = _('لص') # Thief
        elif effective_level < 15:
            title = _('بلطجي') # Thug
        elif effective_level < 20:
            title = _('مجرم') # Criminal
        elif effective_level < 25:
            title = _('قاتل مأجور') # Hitman
        elif effective_level < 30:
            title = _('جندي') # Soldier
        elif effective_level < 40:
            title = _('كابتن') # Captain
        elif effective_level < 50:
            title = _('محترف') # Professional
        elif effective_level < 65:
            title = _('مستشار') # Consigliere
        elif effective_level < 80:
            title = _('وكيل') # Underboss
        elif effective_level < 100:
            title = _('زعيم') # Boss
        else:
            title = _('عراب') # Godfather

        if has_request_context():
            g._rank_title_cache[self.id] = title
        return title

    @property
    def elite_reservation_until(self):
        seat = get_active_elite_seat(self.id)
        if not seat:
            return None
        return seat.reserved_until
