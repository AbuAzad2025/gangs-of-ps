from sqlalchemy.exc import IntegrityError
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum
from flask_babel import _
from flask import current_app, has_request_context, g
from datetime import datetime, timezone, timedelta
from sqlalchemy import UniqueConstraint, func


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
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        unique=True,
        index=True)
    reserved_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(
            timezone.utc), onupdate=lambda: datetime.now(
            timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint(
            'title_key',
            'seat_index',
            name='uq_elite_title_seat_title_index'),
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
            try:
                with db.session.begin_nested():
                    for i in range(existing + 1, quota + 1):
                        db.session.add(
                            EliteTitleSeat(
                                title_key=title_key,
                                seat_index=i))
                    db.session.flush()
                changed = True
            except IntegrityError:
                pass

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
            key = (-eff, -int(user.level or 0), -int(rp or 0), -
                   int(user.exp or 0), int(user.id))
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
        # Get potential free seats (snapshot)
        free_seats_ids = [
            s.id for s in EliteTitleSeat.query.filter_by(
                title_key=title_key, user_id=None).order_by(
                EliteTitleSeat.seat_index.asc()).all()]

        for seat_id in free_seats_ids:
            # Pick candidate based on snapshot
            cand_snapshot = pick_candidate(title_key, min_effective_level)
            if not cand_snapshot:
                return

            try:
                with db.session.begin_nested():
                    # Lock the seat
                    seat = db.session.query(EliteTitleSeat).filter_by(
                        id=seat_id).with_for_update().first()
                    if not seat or seat.user_id is not None:
                        continue  # Seat taken in the meantime

                    # Lock the candidate
                    cand = db.session.query(User).filter_by(
                        id=cand_snapshot.id).with_for_update().first()
                    if not cand:
                        continue  # User gone

                    # Check if user already has a seat (prevent thrashing/race)
                    # In Read Committed, this sees changes from other committed
                    # transactions.
                    existing_seats = EliteTitleSeat.query.filter_by(
                        user_id=cand.id).all()
                    if existing_seats:
                        continue

                    # Clear user's other seats
                    clear_user_seats(cand.id)
                    db.session.flush()

                    # Double check if seat is still free (redundant with lock
                    # but safe)
                    if seat.user_id is None:
                        seat.user_id = cand.id
                        seat.reserved_until = None
                        db.session.flush()
                        changed = True
            except IntegrityError:
                # Race condition: Candidate assigned elsewhere or seat taken by
                # unique constraint
                pass
            except Exception:
                # Log error or ignore
                pass

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
    gender = db.Column(db.String(10), default='male')  # 'male', 'female'
    birthdate = db.Column(db.Date, nullable=True)
    last_seen = db.Column(db.DateTime, index=True)
    country = db.Column(db.String(2), default='PS')  # ISO 2-letter code
    # Optional for now, required for verification
    email = db.Column(db.String(120), unique=True, nullable=True)
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
    health = db.Column(db.Integer, default=30000)
    max_health = db.Column(db.Integer, default=30000)
    brave = db.Column(db.Integer, default=10)  # For attacks
    max_brave = db.Column(db.Integer, default=10)

    # Combat Stats
    strength = db.Column(db.Integer, default=10)
    defense = db.Column(db.Integer, default=10)
    agility = db.Column(db.Integer, default=10)
    intelligence = db.Column(db.Integer, default=10)
    driving_skill = db.Column(db.Integer, default=1)  # New stat for racing
    playstyle = db.Column(db.String(20), default='fighter', index=True)

    # Banking & Status
    bank_balance = db.Column(db.BigInteger, default=0)
    jail_until = db.Column(db.DateTime, nullable=True)
    hospital_until = db.Column(db.DateTime, nullable=True)
    jail_escape_attempts = db.Column(db.Integer, default=0)
    jail_escape_attempts_date = db.Column(db.Date, nullable=True)
    jail_escape_last_at = db.Column(db.DateTime, nullable=True)
    jail_gilboa_attempts = db.Column(db.Integer, default=0)
    jail_gilboa_attempts_date = db.Column(db.Date, nullable=True)
    jail_gilboa_last_at = db.Column(db.DateTime, nullable=True)

    # Daily Limits
    daily_money_earned = db.Column(db.BigInteger, default=0)
    daily_money_date = db.Column(
        db.Date, default=lambda: datetime.now(
            timezone.utc).date())
    daily_bullets_purchased = db.Column(db.Integer, default=0)
    gym_until = db.Column(db.DateTime, nullable=True)
    # Stores JSON for partial rewards logic
    gym_activity = db.Column(db.String(512), nullable=True)
    gym_sessions_count = db.Column(db.Integer, default=0)
    gym_sessions_date = db.Column(db.Date, nullable=True)
    gym_speedups_count = db.Column(db.Integer, default=0)
    gym_speedups_date = db.Column(db.Date, nullable=True)

    # Status Effects
    is_safe_house_active = db.Column(db.Boolean, default=False)
    safe_house_until = db.Column(db.DateTime, nullable=True)
    is_admin_protected = db.Column(db.Boolean, default=False)
    heat_points = db.Column(db.Integer, default=0)
    heat_updated_at = db.Column(db.DateTime, nullable=True, index=True)
    is_disguised = db.Column(db.Boolean, default=False)
    disguise_until = db.Column(db.DateTime, nullable=True)
    casino_luck_until = db.Column(db.DateTime, nullable=True)
    active_hostess_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'hostesses.id',
            use_alter=True,
            name='fk_user_active_hostess_id'),
        nullable=True,
        index=True)

    # Security
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    # VIP subscription expiry (null = lifetime / legacy VIP)
    vip_until = db.Column(db.DateTime, nullable=True, index=True)

    # Optimistic Locking
    version = db.Column(db.Integer, nullable=False, default=0)

    __mapper_args__ = {
        "version_id_col": version
    }

    # Admin/Moderation
    is_ghost_mode = db.Column(db.Boolean, default=False)
    banned_until = db.Column(db.DateTime, nullable=True)
    ban_reason = db.Column(db.String(255), nullable=True)
    is_suspicious = db.Column(db.Boolean, default=False)
    is_chat_banned = db.Column(db.Boolean, default=False)
    chat_muted_until = db.Column(db.DateTime, nullable=True, index=True)

    # Social
    gang_id = db.Column(
        db.Integer,
        db.ForeignKey(
            'gang.id',
            use_alter=True,
            name='fk_user_gang_id'),
        index=True)
    location_id = db.Column(
        db.Integer,
        db.ForeignKey('location.id'),
        default=1,
        index=True)

    # Referrals
    referral_code = db.Column(
        db.String(16),
        unique=True,
        nullable=True,
        index=True)
    referred_by_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        index=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)
    last_seen = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc),
        index=True)
    last_daily_reward = db.Column(db.DateTime, index=True)
    daily_streak = db.Column(db.Integer, default=0)
    last_chase = db.Column(db.DateTime)
    crime_cooldown_until = db.Column(db.DateTime)
    organized_crime_cooldown_until = db.Column(db.DateTime)
    last_crime = db.Column(db.DateTime, index=True)
    last_travel = db.Column(db.DateTime, index=True)
    last_gym_training = db.Column(db.DateTime)
    last_attack = db.Column(db.DateTime)

    # Relationships
    location = db.relationship('Location', foreign_keys=[location_id])
    assets = db.relationship('Asset', backref='owner', lazy=True)
    sent_messages = db.relationship(
        'Message',
        foreign_keys='Message.sender_id',
        backref='sender',
        lazy=True)
    received_messages = db.relationship(
        'Message',
        foreign_keys='Message.receiver_id',
        backref='receiver',
        lazy=True)
    unlocked_achievements = db.relationship(
        'UserAchievement',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan')
    referrals = db.relationship(
        'User',
        backref=db.backref(
            'referrer',
            remote_side=[id]),
        lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def age(self):
        if not self.birthdate:
            return None
        today = datetime.now(timezone.utc).date()
        return today.year - self.birthdate.year - \
            ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))

    def __repr__(self):
        return f'<User {self.username}>'

    def apply_developer_power(self):
        if self.role != UserRole.DEVELOPER:
            return

        now = datetime.now(timezone.utc)

        # Prepare changes for ResourceService
        changes = {
            'money': max(self.money or 0, 10_000_000_000) - (self.money or 0),
            'bullets': max(self.bullets or 0, 10_000_000) - (self.bullets or 0),
            'diamonds': max(self.diamonds or 0, 10_000_000) - (self.diamonds or 0),
            'bank_balance': max(self.bank_balance or 0, 10_000_000_000) - (self.bank_balance or 0),
            'energy': max(self.max_energy or 100, 10000) - (self.energy or 0),
            'health': max(self.max_health or 100, 10000) - (self.health or 0),
            'brave': max(self.max_brave or 10, 1000) - (self.brave or 0),
            'exp': - (self.exp or 0)  # Reset exp
        }

        # Calculate stat changes
        # Note: ResourceService doesn't support generic stats like strength yet in 'changes' map
        # unless we add them to ResourceService validation or just trust it if we map them?
        # ResourceService checks 'if hasattr(user, res)'. So it supports any
        # attribute.

        changes['strength'] = max(
            self.strength or 0, 9999) - (self.strength or 0)
        changes['defense'] = max(self.defense or 0, 9999) - (self.defense or 0)
        changes['agility'] = max(self.agility or 0, 9999) - (self.agility or 0)
        changes['intelligence'] = max(
            self.intelligence or 0, 9999) - (self.intelligence or 0)
        changes['driving_skill'] = max(
            self.driving_skill or 1, 100) - (self.driving_skill or 0)

        # Filter out 0 changes to avoid cluttering logs
        changes = {k: v for k, v in changes.items() if v != 0}

        # Prepare direct field updates
        set_fields = {
            'is_verified': True,
            'verified_on': now,
            'level': max(
                self.level or 1,
                100),
            'max_energy': max(
                self.max_energy or 100,
                10000),
            'max_health': max(
                self.max_health or 100,
                10000),
            'max_brave': max(
                self.max_brave or 10,
                1000),
            'jail_until': None,
            'hospital_until': None,
            'gym_until': None,
            'crime_cooldown_until': None,
            'is_safe_house_active': True,
            'safe_house_until': (
                now +
                timedelta(
                    days=3650)).replace(
                tzinfo=None)}

        from services.resource_service import ResourceService

        # Use modify_resources
        # We don't use expected_version here because developer power is absolute and manual.
        # Also, we are inside the model method, so 'self' is already loaded.
        # But ResourceService re-loads 'self' with lock.
        # We should pass self.id.

        ResourceService.modify_resources(
            self.id,
            changes,
            'developer_power',
            auto_commit=True,
            set_fields=set_fields)

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

        elapsed_minutes = int(
            max(0, (now_naive - updated_at).total_seconds()) // 60)
        try:
            decay_per_min = float(
                SystemConfig.get_value(
                    "heat_decay_per_minute",
                    "0.10") or 0.10)
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

    def has_active_vip(self, now=None):
        from services.vip_service import user_has_active_vip
        return user_has_active_vip(self, now=now)

    def unlock_achievement(self, key, title, description=None, points=0):
        from models.achievement import Achievement, UserAchievement

        achievement = Achievement.query.filter_by(key=key).first()
        if not achievement:
            achievement = Achievement(
                key=key,
                title=title,
                description=description,
                points=points)
            db.session.add(achievement)
            db.session.flush()

        existing = UserAchievement.query.filter_by(
            user_id=self.id, achievement_id=achievement.id).first()
        if existing:
            return existing

        ua = UserAchievement(user_id=self.id, achievement_id=achievement.id)
        db.session.add(ua)
        return ua

    @property
    def achievements(self):
        try:
            return [
                ua.achievement for ua in (
                    self.unlocked_achievements or []) if ua.achievement]
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
            self.max_health += 3000
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

        if leveled_up and self.level >= 5:
            # Check for referral reward
            try:
                from models.referral import Referral
                from services.resource_service import ResourceService
                from models.social import Notification

                referral = Referral.query.filter_by(
                    referred_id=self.id, status='pending').first()
                if referral:
                    referral.status = 'completed'
                    db.session.add(referral)

                    # Reward Referrer: 50,000$ + 50 Diamonds
                    ResourceService.modify_resources(
                        referral.referrer_id,
                        {'money': 50000, 'diamonds': 50},
                        'referral_level_bonus',
                        auto_commit=False
                    )

                    # Notify Referrer
                    notif = Notification(
                        user_id=referral.referrer_id,
                        title='مكافأة إحالة!',
                        message=(
                            f"صديقك {self.username} وصل للمستوى 5! حصلت على 50,000$ و 50 ماسة."
                        ),
                        type='success')
                    db.session.add(notif)
            except Exception as e:
                current_app.logger.error(f"Error in referral reward: {e}")

        return leveled_up

    def regenerate_resources(self):
        """
        Calculates and applies passive resource regeneration based on time elapsed.
        Should be called on every request.
        """
        now = datetime.now(timezone.utc)

        # --- Energy Regeneration ---
        # Rate: 1 Energy per 2 minutes
        energy_rate_minutes = 2
        energy_amount = 1

        if not self.last_energy_update:
            self.last_energy_update = now

        if self.energy < self.max_energy:
            last_update = self.last_energy_update
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            elapsed = (now - last_update).total_seconds()
            cycles = int(elapsed // (energy_rate_minutes * 60))

            if cycles > 0:
                gain = cycles * energy_amount
                # Don't exceed max
                actual_gain = min(gain, self.max_energy - self.energy)

                if actual_gain > 0:
                    self.energy += actual_gain
                    # Update timestamp to the time of the last full cycle to
                    # preserve partial progress
                    self.last_energy_update = last_update + \
                        timedelta(seconds=cycles * energy_rate_minutes * 60)
                else:
                    self.last_energy_update = now
        else:
            self.last_energy_update = now

        # --- Health Regeneration ---
        # Rate: 5% per 5 minutes
        health_rate_minutes = 5
        health_pct = 0.05

        if not self.last_health_update:
            self.last_health_update = now

        if self.health < self.max_health:
            last_update = self.last_health_update
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            elapsed = (now - last_update).total_seconds()
            cycles = int(elapsed // (health_rate_minutes * 60))

            if cycles > 0:
                amount_per_cycle = max(1, int(self.max_health * health_pct))
                gain = cycles * amount_per_cycle
                actual_gain = min(gain, self.max_health - self.health)

                if actual_gain > 0:
                    self.health += actual_gain
                    self.last_health_update = last_update + \
                        timedelta(seconds=cycles * health_rate_minutes * 60)
                else:
                    self.last_health_update = now
        else:
            self.last_health_update = now

    def add_rank_points(self, points=0):
        if points and points > 0:
            try:
                from models.gameplay import UserProgress
                # Atomic update to prevent race conditions
                rows = UserProgress.query.filter_by(user_id=self.id).update(
                    {UserProgress.rank_points: UserProgress.rank_points + points},
                    synchronize_session=False
                )
                if rows == 0:
                    # Record doesn't exist, try to create it
                    # Lock to prevent race on insert if possible, but simple
                    # insert is usually fine with unique constraint
                    try:
                        progress = UserProgress(
                            user_id=self.id, rank_points=points)
                        db.session.add(progress)
                        db.session.flush()
                    except Exception:
                        # Might have been created concurrently
                        db.session.rollback()  # Rollback the flush failure
                        # Retry update
                        UserProgress.query.filter_by(user_id=self.id).update(
                            {UserProgress.rank_points: UserProgress.rank_points + points},
                            synchronize_session=False
                        )
            except Exception:
                # If something goes wrong, we don't want to kill the whole session if this is a side effect
                # But we should probably log it.
                pass

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
        except BaseException:
            return 0

    @property
    def is_super_admin(self):
        return self.role in [UserRole.SUPER_ADMIN, UserRole.DEVELOPER]

    @property
    def is_admin(self):
        return self.role in [
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DEVELOPER]

    @property
    def is_moderator(self):
        return self.role in [
            UserRole.MODERATOR,
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.DEVELOPER]

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
                progress = UserProgress.query.filter_by(
                    user_id=self.id).first()
                if progress:
                    rp = progress.rank_points
            except Exception:
                db.session.rollback()
                rp = 0
            effective_level = self.level + (rp // 50)
            rank = UserRank.query.filter(
                UserRank.min_level <= effective_level).order_by(
                UserRank.min_level.desc()).first()
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
        except BaseException:
            pass

        try:
            from models.gameplay import UserProgress
            rp = 0
            try:
                progress = UserProgress.query.filter_by(
                    user_id=self.id).first()
                if progress:
                    rp = progress.rank_points
            except BaseException:
                rp = 0
            effective_level = self.level + (rp // 50)
        except BaseException:
            effective_level = self.level
        elite_key = None
        try:
            seat = get_active_elite_seat(self.id)
            elite_key = seat.title_key if seat else None
        except Exception:
            elite_key = None

        if effective_level >= 100:
            if elite_key == "godfather":
                title = _('عراب')  # Godfather
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            if elite_key == "boss":
                title = _('زعيم')  # Boss
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            title = _('وكيل')  # Underboss
            if has_request_context():
                g._rank_title_cache[self.id] = title
            return title
        elif effective_level >= 80:
            if elite_key == "boss":
                title = _('زعيم')  # Boss
                if has_request_context():
                    g._rank_title_cache[self.id] = title
                return title
            title = _('وكيل')  # Underboss
            if has_request_context():
                g._rank_title_cache[self.id] = title
            return title

        if effective_level < 3:
            title = _('متشرد')  # Hobo
        elif effective_level < 5:
            title = _('نشال')  # Pickpocket
        elif effective_level < 10:
            title = _('لص')  # Thief
        elif effective_level < 15:
            title = _('بلطجي')  # Thug
        elif effective_level < 20:
            title = _('مجرم')  # Criminal
        elif effective_level < 25:
            title = _('قاتل مأجور')  # Hitman
        elif effective_level < 30:
            title = _('جندي')  # Soldier
        elif effective_level < 40:
            title = _('كابتن')  # Captain
        elif effective_level < 50:
            title = _('محترف')  # Professional
        elif effective_level < 65:
            title = _('مستشار')  # Consigliere
        elif effective_level < 80:
            title = _('وكيل')  # Underboss
        elif effective_level < 100:
            title = _('زعيم')  # Boss
        else:
            title = _('عراب')  # Godfather

        if has_request_context():
            g._rank_title_cache[self.id] = title
        return title

    @property
    def elite_reservation_until(self):
        seat = get_active_elite_seat(self.id)
        if not seat:
            return None
        return seat.reserved_until
