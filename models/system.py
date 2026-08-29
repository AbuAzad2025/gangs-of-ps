from extensions import db
from datetime import datetime, timedelta, timezone


DEFAULT_SYSTEM_CONFIG = {
    "game_name": "عصابات فلسطين",
    "game_tagline": "لعبة استراتيجية الجريمة والهيمنة",
    "game_status": "online",
    "app_version": "1.0.0",
    "support_email": "support@gangsofpalestine.com",
    "economy_daily_money_limit": "2500000",
    "starter_money": "2500",
    "starter_energy": "100",
    "starter_max_energy": "100",
    "starter_bullets": "50",
    "starter_diamonds": "0",
    "daily_reward_base_money_per_level": "120",
    "daily_reward_base_energy": "22",
    "daily_reward_base_exp": "14",
    "daily_reward_streak_step_pct": "0.12",
    "crime_level_money_multiplier": "0.03",
    "crime_level_exp_multiplier": "0.025",
    "crime_early_level_reward_boost_pct": "0.22",
    "crime_early_level_cap": "5",
    "elite_sync_interval_seconds": "60",
    "organized_crimes_enabled": "true",
    "organized_crimes_allow_non_gang": "true",
    "organized_crimes_min_creator_rank_level": "20",
    "vip_monthly_cost_diamonds": "80",
    "vip_lifetime_cost_diamonds": "250",
    "vip_upgrade_cost_diamonds": "250",
    "current_season_id": "1",
    "current_season_name": "الموسم 1",
    "season_ends_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    "world_event_active": "false",
    "world_event_title": "حدث عالمي",
    "world_event_type": "general",
    "world_event_description": "حدث عالمي مستجد في المدينة.",
    "world_event_money_bonus_pct": "0",
    "world_event_icon": "fa-bolt",
    "bank_fee_tier1_threshold": "40000",
    "bank_fee_tier2_threshold": "180000",
    "bank_fee_tier1_pct": "0.005",
    "bank_fee_tier2_pct": "0.012",
    "maintenance_multiplier": "1.0",
    "early_game_fee_grace_level": "5",
    "early_game_fee_discount_pct": "0.5",
    "early_game_maintenance_grace_level": "3",
    "early_game_maintenance_discount_pct": "0.5",
    "global_data_cache_seconds": "5",
}


class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))

    @staticmethod
    def get_value(key, default=None):
        try:
            config = SystemConfig.query.filter_by(key=key).first()
            return config.value if config else default
        except Exception:
            db.session.rollback()
            return default

    @staticmethod
    def set_value(key, value, description=None):
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            config = SystemConfig(key=key)
            db.session.add(config)
        config.value = str(value)
        if description:
            config.description = description
        db.session.commit()

    @staticmethod
    def ensure_defaults():
        """Create a baseline settings set so the game launches with coherent defaults."""
        try:
            for key, value in DEFAULT_SYSTEM_CONFIG.items():
                if SystemConfig.get_value(key, None) is None:
                    SystemConfig.set_value(key, value, "Game default")
            return True
        except Exception:
            db.session.rollback()
            return False


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    def __repr__(self):
        return f'<Announcement {self.title}>'


class SecurityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # e.g., 'master_key_success', 'master_key_fail', 'brute_force'
    event_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50))
    details = db.Column(db.Text)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(
            timezone.utc))

    def __repr__(self):
        return f'<SecurityLog {self.event_type} at {self.timestamp}>'
