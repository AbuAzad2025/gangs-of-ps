"""VIP subscription helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from extensions import db
from models.user import User, UserRole


def _aware(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def user_has_active_vip(user: User, now=None) -> bool:
    if not user or user.role.value < UserRole.SUBSCRIBER.value:
        return False
    until = getattr(user, "vip_until", None)
    if until is None:
        return True
    now = now or datetime.now(timezone.utc)
    return _aware(until) > now


def expire_vip_if_needed(user: User, now=None) -> bool:
    """Downgrade expired monthly VIP. Returns True if still VIP."""
    if not user or user.role.value < UserRole.SUBSCRIBER.value:
        return False
    until = getattr(user, "vip_until", None)
    if until is None:
        return True
    now = now or datetime.now(timezone.utc)
    if _aware(until) > now:
        return True
    user.role = UserRole.USER
    db.session.add(user)
    return False


def grant_vip(user_id: int, days: int | None = None, *, lifetime: bool = False) -> bool:
    user = db.session.get(User, user_id)
    if not user:
        return False
    user.role = UserRole.SUBSCRIBER
    if lifetime or days is None:
        user.vip_until = None
    else:
        base = _aware(user.vip_until) or datetime.now(timezone.utc)
        if base < datetime.now(timezone.utc):
            base = datetime.now(timezone.utc)
        user.vip_until = base + timedelta(days=max(1, int(days)))
    db.session.add(user)
    return True
