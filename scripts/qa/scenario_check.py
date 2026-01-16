import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."))
sys.path.insert(0, PROJECT_ROOT)


@dataclass
class StepResult:
    name: str
    method: str
    url: str
    status: int


def _ok_status(code):
    return code in (200, 302, 303) or (200 <= code < 300)


def _req(client, method, url, data=None, follow=True):
    if method == "GET":
        resp = client.get(url, follow_redirects=follow)
    elif method == "POST":
        resp = client.post(url, data=data or {}, follow_redirects=follow)
    else:
        raise ValueError(method)
    return resp


def _login(client, username, password):
    resp = client.post(
        "/login",
        data={
            "username": username,
            "password": password},
        follow_redirects=True)
    return resp


def _ensure_user(username, password, role=None):
    from extensions import db
    from models import User, UserRole

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(username=username, created_at=datetime.now(timezone.utc))
        user.set_password(password)
        user.is_verified = True
        user.verified_on = datetime.now(timezone.utc)
        if role is not None:
            user.role = role
        db.session.add(user)
        db.session.commit()
    else:
        user.set_password(password)
        user.failed_login_attempts = 0
        user.locked_until = None
        if role is not None:
            user.role = role
        user.is_verified = True
        user.verified_on = datetime.now(timezone.utc)
        db.session.commit()

    if role == UserRole.DEVELOPER:
        try:
            user.apply_developer_power()
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    return user


def _ensure_active_vehicle(user_id):
    from extensions import db
    from models import UserVehicle, Vehicle

    v = Vehicle.query.filter_by(
        is_active=True).order_by(
        Vehicle.id.asc()).first()
    if not v:
        return None

    existing = UserVehicle.query.filter_by(
        user_id=user_id).order_by(
        UserVehicle.id.desc()).all()
    for uv in existing:
        uv.is_active = False
    db.session.commit()

    uv = UserVehicle(
        user_id=user_id,
        vehicle_id=v.id,
        is_active=True,
        condition=100)
    db.session.add(uv)
    db.session.commit()
    return uv


def _ensure_user_item(user_id):
    from extensions import db
    from models import Item, UserItem

    item = Item.query.filter(Item.type.in_(
        ["weapon", "armor"])).order_by(Item.id.asc()).first()
    if not item:
        return None

    ui = UserItem.query.filter_by(user_id=user_id, item_id=item.id).first()
    if not ui:
        ui = UserItem(
            user_id=user_id,
            item_id=item.id,
            quantity=1,
            is_equipped=False,
            condition=100)
        db.session.add(ui)
        db.session.commit()
    return ui


def _pick_location_id():
    from models import Location

    loc = Location.query.order_by(Location.id.asc()).first()
    if not loc:
        return None
    loc2 = Location.query.order_by(Location.id.desc()).first()
    if loc2 and loc2.id != loc.id:
        return loc2.id
    return loc.id


def _pick_market_asset_id():
    from models import MarketAsset

    a = MarketAsset.query.order_by(MarketAsset.id.asc()).first()
    return a.id if a else None


def _cleanup_user(username):
    from extensions import db
    from models import (
        User,
        UserVehicle,
        UserItem,
        UserInvestment,
        SpotOrder,
        FuturesPosition,
        CasinoGame,
        RaceParticipant,
        Race,
        Message,
    )

    u = User.query.filter_by(username=username).first()
    if not u:
        return

    try:
        RaceParticipant.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        races = Race.query.filter_by(creator_id=u.id).all()
        for r in races:
            RaceParticipant.query.filter_by(
                race_id=r.id).delete(
                synchronize_session=False)
            db.session.delete(r)

        CasinoGame.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        SpotOrder.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        FuturesPosition.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        UserInvestment.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        UserItem.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        UserVehicle.query.filter_by(
            user_id=u.id).delete(
            synchronize_session=False)
        Message.query.filter(
            (Message.sender_id == u.id) | (
                Message.receiver_id == u.id)).delete(
            synchronize_session=False)
        db.session.delete(u)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def run():
    from factory import create_app
    from extensions import db
    from models import FuturesPosition, SpotOrder

    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    app.config.setdefault("RATELIMIT_ENABLED", False)

    results = []
    failures = []

    with app.app_context():
        qa1_pass = "QaPass_12345678"
        qa2_pass = "QaPass_12345678"

        qa1 = _ensure_user("QA_1", qa1_pass)
        qa2 = _ensure_user("QA_2", qa2_pass)
        qa1_id = qa1.id
        qa2_id = qa2.id

        qa1.money = max(int(getattr(qa1, "money", 0) or 0), 5_000_000)
        qa1.bank_balance = max(
            int(getattr(qa1, "bank_balance", 0) or 0), 1_000_000)
        qa1.energy = max(int(getattr(qa1, "energy", 0) or 0), 10_000)
        qa1.max_energy = max(int(getattr(qa1, "max_energy", 0) or 100), 10_000)
        qa1.health = max(int(getattr(qa1, "health", 0) or 0), 10_000)
        qa1.max_health = max(int(getattr(qa1, "max_health", 0) or 100), 10_000)

        qa2.money = max(int(getattr(qa2, "money", 0) or 0), 5_000_000)
        qa2.bank_balance = max(
            int(getattr(qa2, "bank_balance", 0) or 0), 1_000_000)
        qa2.energy = max(int(getattr(qa2, "energy", 0) or 0), 10_000)
        qa2.max_energy = max(int(getattr(qa2, "max_energy", 0) or 100), 10_000)
        qa2.health = max(int(getattr(qa2, "health", 0) or 0), 10_000)
        qa2.max_health = max(int(getattr(qa2, "max_health", 0) or 100), 10_000)

        qa1.jail_until = None
        qa1.hospital_until = None
        qa1.gym_until = None
        qa1.gym_activity = None
        qa2.jail_until = None
        qa2.hospital_until = None
        qa2.gym_until = None
        qa2.gym_activity = None
        db.session.commit()

        uv1 = _ensure_active_vehicle(qa1_id)
        uv2 = _ensure_active_vehicle(qa2_id)
        ui1 = _ensure_user_item(qa1_id)
        ui2 = _ensure_user_item(qa2_id)
        uv1_id = uv1.id if uv1 else None
        uv2_id = uv2.id if uv2 else None
        ui1_id = ui1.id if ui1 else None
        ui2_id = ui2.id if ui2 else None

        location_id = _pick_location_id()
        asset_id = _pick_market_asset_id()

    def step(client, name, method, url, data=None, follow=False):
        resp = _req(client, method, url, data=data, follow=follow)
        results.append(
            StepResult(
                name=name,
                method=method,
                url=url,
                status=resp.status_code))
        if not _ok_status(resp.status_code):
            failures.append((name, method, url, resp.status_code))
        return resp

    try:
        client1 = app.test_client()
        client2 = app.test_client()

        step(
            client1,
            "login_qa1",
            "POST",
            "/login",
            data={
                "username": "QA_1",
                "password": "QaPass_12345678"})
        step(
            client2,
            "login_qa2",
            "POST",
            "/login",
            data={
                "username": "QA_2",
                "password": "QaPass_12345678"})

        step(client1, "hara", "GET", "/hara")
        step(client1, "garage", "GET", "/garage")
        step(client1, "bank_index", "GET", "/bank/")
        step(
            client1,
            "bank_deposit",
            "POST",
            "/bank/deposit",
            data={
                "amount": "1000"})
        step(
            client1,
            "bank_withdraw",
            "POST",
            "/bank/withdraw",
            data={
                "amount": "500"})

        step(client1, "gym_index", "GET", "/gym/")
        step(client1, "gym_train_strength", "POST", "/gym/train/strength")
        step(client1, "gym_cancel", "POST", "/gym/cancel")

        if ui1_id:
            step(client1, "inventory_index", "GET", "/inventory/")
            step(
                client1,
                "inventory_equip",
                "POST",
                f"/inventory/equip/{ui1_id}")
            step(
                client1,
                "inventory_unequip",
                "POST",
                f"/inventory/unequip/{ui1_id}")

        if location_id:
            step(client1, "travel_index", "GET", "/travel/")
            step(client1, "travel_fly", "POST", f"/travel/fly/{location_id}")

        if asset_id:
            step(client1, "market_index", "GET", "/market/")
            step(
                client1,
                "market_trade",
                "GET",
                f"/market/trade/{asset_id}?tab=spot")
            step(
                client1,
                "market_spot_buy_market",
                "POST",
                f"/market/place_order/{asset_id}",
                data={"trade_type": "market", "type": "buy", "amount": "10"},
            )
            step(
                client1,
                "market_futures_open_long",
                "POST",
                f"/market/open_futures/{asset_id}",
                data={"type": "long", "leverage": "10", "amount": "10"},
            )

            with app.app_context():
                pos = FuturesPosition.query.filter_by(
                    user_id=qa1_id, asset_id=asset_id, is_open=True).order_by(
                    FuturesPosition.id.desc()).first()
                if pos:
                    step(client1, "market_futures_close", "POST",
                         f"/market/close_futures/{pos.id}")
                order = SpotOrder.query.filter_by(
                    user_id=qa1_id, asset_id=asset_id, status="open").order_by(
                    SpotOrder.id.desc()).first()
                if order:
                    step(client1, "market_cancel_order", "POST",
                         f"/market/cancel_order/{order.id}")

        step(client1, "casino_index", "GET", "/casino/")
        step(client1, "casino_roulette", "GET", "/casino/roulette")
        step(
            client1,
            "casino_roulette_spin",
            "POST",
            "/casino/roulette/spin",
            data={
                "bet_amount": "10",
                "bet_type": "red"})

        step(client1, "casino_blackjack", "GET", "/casino/blackjack")
        step(
            client1,
            "casino_blackjack_deal",
            "POST",
            "/casino/blackjack/deal",
            data={
                "bet": "10"})
        step(client1, "casino_blackjack_hit", "POST", "/casino/blackjack/hit")
        step(client1, "casino_blackjack_stand",
             "POST", "/casino/blackjack/stand")
        step(client1, "casino_blackjack_reset",
             "GET", "/casino/blackjack/reset")

        step(client1, "racing_index", "GET", "/casino/racing/")
        create_resp = step(
            client1,
            "racing_create",
            "POST",
            "/casino/racing/create",
            data={
                "bet": "100"})
        race_id = None
        loc = create_resp.headers.get("Location") or ""
        if "/casino/racing/room/" in loc:
            try:
                race_id = int(loc.rsplit("/", 1)[-1])
            except Exception:
                race_id = None

        if race_id:
            step(client2, "racing_join", "POST",
                 f"/casino/racing/join/{race_id}")
            step(client1, "racing_start", "POST",
                 f"/casino/racing/start/{race_id}")
            step(
                client1,
                "racing_room",
                "GET",
                f"/casino/racing/room/{race_id}")

        if uv1_id:
            step(client1, "garage_sell", "POST", f"/sell_car/{uv1_id}")

        dev_client = app.test_client()
        step(dev_client, "debug_login_azad", "GET", "/debug_login")
        step(dev_client, "developer_index", "GET", "/developer")
        step(dev_client, "developer_verify_get", "GET", "/developer/verify")
        now = datetime.now()
        master = f"Azad@1983@{now:%Y}@{now:%m}@{now:%d}"
        step(
            dev_client,
            "developer_verify_post",
            "POST",
            "/developer/verify",
            data={
                "password": master})
        step(dev_client, "admin_index", "GET", "/admin/")

    finally:
        with app.app_context():
            _cleanup_user("QA_1")
            _cleanup_user("QA_2")

    print("SCENARIO_CHECK_REPORT")
    for r in results:
        print(f"{r.status} {r.method} {r.url} :: {r.name}")

    if failures:
        print("FAILURES")
        for name, method, url, status in failures:
            print(f"{status} {method} {url} :: {name}")
        raise SystemExit(1)


if __name__ == "__main__":
    run()
