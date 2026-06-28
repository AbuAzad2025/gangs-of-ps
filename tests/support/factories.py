"""Reusable test data builders for game scenarios."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from models.user import User, UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_user(
    db,
    *,
    username: str = 'player1',
    email: str | None = None,
    password: str = 'password123',
    role: UserRole = UserRole.USER,
    money: int = 100,
    bank_balance: int = 0,
    diamonds: int = 0,
    level: int = 1,
    exp: int = 0,
    is_verified: bool = True,
    **extra: Any,
) -> User:
    user = User(
        username=username,
        email=email or f'{username}@test.example',
        role=role,
        money=money,
        bank_balance=bank_balance,
        diamonds=diamonds,
        level=level,
        exp=exp,
        is_verified=is_verified,
        **extra,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    user_id = int(user.id)
    db.session.commit()
    return db.session.get(User, user_id)


def make_user_id(db, **kwargs) -> int:
    """Stable user id for tests that survive session.remove() after HTTP."""
    user = make_user(db, **kwargs)
    return int(user.__dict__['id'])


def make_jailed_user(db, *, minutes: int = 60, **kwargs) -> User:
    until = utc_now() + timedelta(minutes=minutes)
    return make_user(db, jail_until=until.replace(tzinfo=None), **kwargs)


def make_hospitalized_user(db, *, minutes: int = 60, **kwargs) -> User:
    until = utc_now() + timedelta(minutes=minutes)
    return make_user(db, hospital_until=until.replace(tzinfo=None), **kwargs)


def make_gym_user(db, *, minutes: int = 60, **kwargs) -> User:
    until = utc_now() + timedelta(minutes=minutes)
    return make_user(db, gym_until=until.replace(tzinfo=None), **kwargs)


def make_admin(db, **kwargs) -> User:
    return make_user(db, username=kwargs.pop('username', 'admin1'), role=UserRole.ADMIN, **kwargs)


def make_moderator(db, **kwargs) -> User:
    return make_user(db, username=kwargs.pop('username', 'mod1'), role=UserRole.MODERATOR, **kwargs)


def make_developer(db, **kwargs) -> User:
    return make_user(db, username=kwargs.pop('username', 'dev1'), role=UserRole.DEVELOPER, **kwargs)


def make_vip_user(db, *, days: int | None = 30, lifetime: bool = False, **kwargs) -> User:
    user = make_user(db, role=UserRole.SUBSCRIBER, **kwargs)
    if lifetime:
        user.vip_until = None
    elif days is not None:
        user.vip_until = (utc_now() + timedelta(days=days)).replace(tzinfo=None)
    db.session.add(user)
    db.session.commit()
    return user
