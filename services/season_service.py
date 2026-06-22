"""Season system — SystemConfig-driven, no extra tables."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from extensions import db
from models.system import SystemConfig
from models.user import User
from sqlalchemy import func


def _now():
    return datetime.now(timezone.utc)


def _cfg(key: str, default: str = "") -> str:
    try:
        return str(SystemConfig.get_value(key, default) or default)
    except Exception:
        return default


def get_current_season() -> Dict[str, Any]:
    now = _now()
    name = _cfg("current_season_name", "الموسم 1")
    try:
        season_id = int(_cfg("current_season_id", "1") or 1)
    except Exception:
        season_id = 1
    ends_raw = _cfg("season_ends_at", "")
    ends_at = None
    if ends_raw:
        try:
            ends_at = datetime.fromisoformat(ends_raw.replace("Z", "+00:00"))
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
        except Exception:
            ends_at = None
    if not ends_at:
        ends_at = now + timedelta(days=30)
    days_left = max(0, (ends_at.date() - now.date()).days)
    return {
        "id": season_id,
        "name": name,
        "ends_at": ends_at,
        "days_left": days_left,
        "active": days_left > 0,
    }


def ensure_season_active() -> Dict[str, Any]:
    """Roll season forward if expired (idempotent)."""
    season = get_current_season()
    if season["active"]:
        return season
    try:
        new_id = int(season["id"]) + 1
    except Exception:
        new_id = 2
    now = _now()
    new_end = now + timedelta(days=30)
    SystemConfig.set_value("current_season_id", str(new_id))
    SystemConfig.set_value("current_season_name", f"الموسم {new_id}")
    SystemConfig.set_value("season_ends_at", new_end.isoformat())
    db.session.commit()
    return get_current_season()


def get_season_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(
            User.id,
            User.username,
            User.level,
            User.exp,
            (User.money + User.bank_balance).label("wealth"),
        )
        .order_by(User.level.desc(), User.exp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "username": r.username,
            "level": int(r.level or 0),
            "exp": int(r.exp or 0),
            "wealth": int(r.wealth or 0),
        }
        for r in rows
    ]


def get_user_season_rank(user_id: int) -> Optional[int]:
    sub = (
        db.session.query(
            User.id,
            func.rank().over(order_by=(User.level.desc(), User.exp.desc())).label("rk"),
        )
        .subquery()
    )
    row = db.session.query(sub.c.rk).filter(sub.c.id == user_id).first()
    return int(row.rk) if row else None
