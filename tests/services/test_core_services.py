from datetime import datetime, timedelta, timezone

from services.requirements import check_requirements


def test_requirements_reports_first_missing_stat_and_hint(app, db):
    from tests.support.factories import make_user
    with app.app_context():
        user = make_user(db, username="requirements-low")
        user.level = 2
        user.exp = 0
        user.intelligence = 1
        user.strength = 1
        user.agility = 1
        result = check_requirements(user, {
        "min_tier": "t3", "min_level": 10, "min_exp": 100,
        "min_intelligence": 5, "min_strength": 5, "min_agility": 5,
        })
    assert result["ok"] is False
    assert result["missing"] == ["tier", "level", "exp", "intelligence", "strength", "agility"]
    assert result["hint_key"] == "daily_tasks"
    assert result["reason"]


def test_requirements_accepts_effective_level_and_all_stats(app, db):
    from tests.support.factories import make_user
    with app.app_context():
        user = make_user(db, username="requirements-high")
        user.level = 20
        user.exp = 200
        user.intelligence = user.strength = user.agility = 10
        result = check_requirements(user, {
        "min_tier": "t3", "min_level": 15, "min_exp": 100,
        "min_intelligence": 5, "min_strength": 5, "min_agility": 5,
        })
    assert result["ok"] is True
    assert result["tier"] == "t3"


def test_world_event_expiry_and_bonus(app):
    from models.system import SystemConfig
    from services.world_event_service import (
        apply_world_event_money_bonus, get_active_world_event)

    with app.app_context():
        for key, value in {
            "world_event_active": "true",
            "world_event_title": "Double payout",
            "world_event_money_bonus_pct": "25",
            "world_event_ends_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
        }.items():
            SystemConfig.set_value(key, value)
        assert get_active_world_event()["title"] == "Double payout"
        assert apply_world_event_money_bonus(200) == 250
        SystemConfig.set_value(
            "world_event_ends_at",
            (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
        assert get_active_world_event() is None
        assert apply_world_event_money_bonus(200) == 200


def test_vip_grant_expire_and_lifetime(app, db):
    from services.vip_service import (
        expire_vip_if_needed, grant_vip, user_has_active_vip)
    from models.user import UserRole

    from tests.support.factories import make_user
    with app.app_context():
        user = make_user(db, username="vip-player")
        assert grant_vip(user.id, days=2)
        assert user.role == UserRole.SUBSCRIBER
        assert user_has_active_vip(user)
        user.vip_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert expire_vip_if_needed(user) is False
        assert user.role == UserRole.USER
        assert grant_vip(user.id, lifetime=True)
        assert user_has_active_vip(user)
        assert grant_vip(999999, days=1) is False
