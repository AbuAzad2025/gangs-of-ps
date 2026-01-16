from models.user import User, UserRole
from factory import create_app
from extensions import db
from config import Config
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _now():
    return datetime.now(timezone.utc)


def _ensure_user(
        username: str,
        password: str,
        role: UserRole,
        level: int) -> User:
    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username)
        db.session.add(user)

    user.role = role
    user.level = int(level)
    user.is_verified = True
    user.verified_on = _now().replace(tzinfo=None)
    user.set_password(password)

    if not user.money or user.money < 500000:
        user.money = 500000
    if not user.diamonds or user.diamonds < 500:
        user.diamonds = 500
    if not user.max_energy:
        user.max_energy = 100
    if not user.max_health:
        user.max_health = 30000
    if not user.max_brave:
        user.max_brave = 10
    if not user.energy:
        user.energy = user.max_energy
    if not user.health:
        user.health = user.max_health
    if not user.brave:
        user.brave = user.max_brave

    return user


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", required=True)
    parser.add_argument("--prefix", default="test")
    parser.add_argument("--create", type=int, default=6)
    parser.add_argument("--jail", type=int, default=3)
    parser.add_argument("--graveyard", type=int, default=1)
    args = parser.parse_args()

    app = create_app(Config)
    with app.app_context():
        now = _now()
        roles = [
            UserRole.USER,
            UserRole.USER,
            UserRole.USER,
            UserRole.MODERATOR,
            UserRole.ADMIN,
            UserRole.DEVELOPER]
        levels = [2, 8, 20, 35, 60, 100]

        users = []
        for i in range(max(1, int(args.create))):
            role = roles[i % len(roles)]
            level = levels[i % len(levels)]
            uname = f"{args.prefix}_u{i + 1:02d}"
            u = _ensure_user(uname, args.password, role, level)
            users.append(u)

        db.session.flush()

        jail_count = max(0, min(len(users), int(args.jail)))
        for i in range(jail_count):
            users[i].jail_until = (
                now + timedelta(minutes=45 + (i * 15))).replace(tzinfo=None)

        grave_count = max(0, min(len(users), int(args.graveyard)))
        for i in range(grave_count):
            idx = len(users) - 1 - i
            users[idx].health = 0
            users[idx].hospital_until = None
            users[idx].jail_until = None

        db.session.commit()


if __name__ == "__main__":
    main()
