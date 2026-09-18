from datetime import datetime, timedelta, timezone

import pytest

from models import (
    Asset,
    Gang,
    GangInvite,
    GangLog,
    MarketAsset,
    SpotOrder,
    UserInvestment,
    User,
)
from tests.support.factories import make_user


class TestGangFlows:
    def test_create_gang_deducts_cash_and_assigns_leader(self, logged_in_client, db, auth_user_id):
        user = db.session.get(User, auth_user_id)
        user.money = 20_000
        db.session.commit()

        response = logged_in_client.post(
            "/gang/create",
            data={"name": "Southside", "description": "A crew", "min_level_req": "2"},
        )

        assert response.status_code == 302
        gang = Gang.query.filter_by(name="Southside").one()
        user = db.session.get(User, auth_user_id)
        assert user.gang_id == gang.id
        assert gang.leader_id == auth_user_id
        assert user.money == 10_000

    def test_create_gang_rejects_missing_name_without_state_change(self, logged_in_client, db, auth_user_id):
        before = db.session.get(User, auth_user_id).money

        response = logged_in_client.post("/gang/create", data={"name": ""})

        assert response.status_code == 302
        assert Gang.query.count() == 0
        assert db.session.get(User, auth_user_id).money == before

    def test_accept_invite_only_changes_invited_user(self, client, app, db):
        leader = make_user(db, username="gangleader", money=50_000)
        invited = make_user(db, username="invitee")
        gang = Gang(name="Invites", leader_id=leader.id, max_members=5)
        db.session.add(gang)
        db.session.flush()
        leader.gang_id = gang.id
        invite = GangInvite(gang_id=gang.id, user_id=invited.id, status="pending")
        db.session.add(invite)
        db.session.commit()

        from tests.support.client_helpers import login_client

        login_client(client, app, invited)
        response = client.post(f"/gang/accept_invite/{invite.id}")

        assert response.status_code == 302
        assert db.session.get(User, invited.id).gang_id == gang.id
        assert db.session.get(GangInvite, invite.id).status == "accepted"
        assert GangLog.query.filter_by(gang_id=gang.id, user_id=invited.id).count() == 1

    def test_donate_and_withdraw_update_balances_and_log(self, client, app, db):
        leader = make_user(db, username="vaultleader", money=1_000)
        gang = Gang(name="Vault", leader_id=leader.id, money=100)
        db.session.add(gang)
        db.session.flush()
        leader.gang_id = gang.id
        db.session.commit()

        from tests.support.client_helpers import login_client

        login_client(client, app, leader)
        assert client.post("/gang/donate", data={"amount": "250"}).status_code == 302
        assert db.session.get(User, leader.id).money == 750
        assert db.session.get(Gang, gang.id).money == 350

        assert client.post("/gang/withdraw", data={"amount": "100"}).status_code == 302
        assert db.session.get(User, leader.id).money == 850
        assert db.session.get(Gang, gang.id).money == 250
        assert GangLog.query.filter_by(gang_id=gang.id).count() == 2

    def test_withdraw_denied_to_non_leader(self, client, app, db):
        leader = make_user(db, username="leader", money=100)
        member = make_user(db, username="member", money=100)
        gang = Gang(name="Permission", leader_id=leader.id, money=500)
        db.session.add(gang)
        db.session.flush()
        leader.gang_id = gang.id
        member.gang_id = gang.id
        db.session.commit()

        from tests.support.client_helpers import login_client

        login_client(client, app, member)
        response = client.post("/gang/withdraw", data={"amount": "100"})

        assert response.status_code == 302
        assert db.session.get(Gang, gang.id).money == 500
        assert db.session.get(User, member.id).money == 100


class TestEconomyFlows:
    def test_buy_property_debits_user_and_creates_owned_copy(self, logged_in_client, db, auth_user_id):
        user = db.session.get(User, auth_user_id)
        user.money = 5_000
        template = Asset(name="Safe House", type="house", value=1_250, income=300, is_active=True)
        db.session.add(template)
        db.session.commit()

        response = logged_in_client.post(f"/economy/buy_property/{template.id}")

        assert response.status_code == 302
        assert db.session.get(User, auth_user_id).money == 3_750
        owned = Asset.query.filter_by(owner_id=auth_user_id).one()
        assert owned.name == template.name
        assert owned.income == 300

    def test_collect_income_credits_net_income_and_sets_collection_time(
        self, logged_in_client, db, auth_user_id
    ):
        user = db.session.get(User, auth_user_id)
        user.money = 100
        asset = Asset(
            name="Business",
            type="house",
            owner_id=auth_user_id,
            value=2_000,
            income=500,
            maintenance_cost=75,
            last_collected=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.session.add(asset)
        db.session.commit()

        response = logged_in_client.post(f"/economy/collect_income/{asset.id}")

        assert response.status_code == 302
        assert db.session.get(User, auth_user_id).money == 525
        assert db.session.get(Asset, asset.id).last_collected is not None

    def test_collect_income_rejects_another_users_property(self, logged_in_client, db, auth_user_id):
        other = make_user(db, username="propertyowner")
        asset = Asset(name="Not Mine", type="house", owner_id=other.id, income=500)
        db.session.add(asset)
        db.session.commit()
        before = db.session.get(User, auth_user_id).money

        response = logged_in_client.post(f"/economy/collect_income/{asset.id}")

        assert response.status_code == 302
        assert db.session.get(User, auth_user_id).money == before


class TestMarketFlows:
    @pytest.fixture
    def market_asset(self, db):
        asset = MarketAsset(
            symbol="TEST",
            name="Test Asset",
            asset_type="stock",
            current_price=100.0,
            last_updated=datetime.now(timezone.utc),
        )
        db.session.add(asset)
        db.session.commit()
        return asset

    def test_market_buy_and_sell_change_cash_and_position(
        self, logged_in_client, db, auth_user_id, market_asset, monkeypatch
    ):
        monkeypatch.setattr("routes.market.update_market_prices", lambda: None)
        user = db.session.get(User, auth_user_id)
        user.money = 10_000
        db.session.commit()

        buy = logged_in_client.post(
            f"/market/place_order/{market_asset.id}",
            data={"trade_type": "market", "type": "buy", "amount": "1000"},
        )
        assert buy.status_code == 302
        investment = UserInvestment.query.filter_by(user_id=auth_user_id, asset_id=market_asset.id).one()
        assert investment.quantity == pytest.approx(10.0)
        assert db.session.get(User, auth_user_id).money == 9_000

        sell = logged_in_client.post(
            f"/market/place_order/{market_asset.id}",
            data={"trade_type": "market", "type": "sell", "amount": "4"},
        )
        assert sell.status_code == 302
        investment = UserInvestment.query.filter_by(user_id=auth_user_id, asset_id=market_asset.id).one()
        assert investment.quantity == pytest.approx(6.0)
        assert db.session.get(User, auth_user_id).money == pytest.approx(9_400)

    def test_limit_buy_reserves_cash_and_invalid_order_does_not_create_order(
        self, logged_in_client, db, auth_user_id, market_asset, monkeypatch
    ):
        monkeypatch.setattr("routes.market.update_market_prices", lambda: None)
        user = db.session.get(User, auth_user_id)
        user.money = 10_000
        db.session.commit()

        response = logged_in_client.post(
            f"/market/place_order/{market_asset.id}",
            data={"trade_type": "limit", "type": "buy", "amount": "5", "price": "100"},
        )
        assert response.status_code == 302
        order = SpotOrder.query.filter_by(user_id=auth_user_id, status="open").one()
        assert order.quantity == 5
        assert db.session.get(User, auth_user_id).money == 9_500

        invalid = logged_in_client.post(
            f"/market/place_order/{market_asset.id}",
            data={"trade_type": "market", "type": "hold", "amount": "100"},
        )
        assert invalid.status_code == 302
        assert SpotOrder.query.filter_by(user_id=auth_user_id).count() == 1
