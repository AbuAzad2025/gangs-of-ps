import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import Config
from factory import create_app
from models.user import User
from services.resource_service import ResourceService


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _find_user(username: str):
    if not username:
        return None
    u = User.query.filter(User.username == username).first()
    if u:
        return u
    return User.query.filter(User.username.ilike(username)).first()


def _pick_second_user(exclude_id: int):
    return (
        User.query.filter(User.id != exclude_id)
        .order_by(User.id.desc())
        .first()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--azad", default="Azad")
    parser.add_argument("--user2", default="")
    parser.add_argument("--minutes_azad", type=int, default=90)
    parser.add_argument("--minutes_user2", type=int, default=60)
    args = parser.parse_args()

    app = create_app(Config)
    with app.app_context():
        now = _now()

        azad = _find_user(args.azad) or _find_user("azad")
        if not azad:
            raise SystemExit("Azad user not found")

        user2 = _find_user(args.user2) if args.user2 else _pick_second_user(azad.id)
        if not user2:
            raise SystemExit("Second user not found")

        azad_until = (now + timedelta(minutes=max(1, int(args.minutes_azad)))).replace(tzinfo=None)
        user2_until = (now + timedelta(minutes=max(1, int(args.minutes_user2)))).replace(tzinfo=None)

        ResourceService.modify_resources(azad.id, {}, "admin_jail", auto_commit=True, set_fields={"jail_until": azad_until})
        ResourceService.modify_resources(user2.id, {}, "admin_jail", auto_commit=True, set_fields={"jail_until": user2_until})


if __name__ == "__main__":
    main()

