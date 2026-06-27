import pytest
from extensions import db


class TestUserModel:
    def test_create_user(self, app, new_user):
        from models.user import User
        user = db.session.get(User, new_user.id)
        assert user is not None
        assert user.username == 'testplayer'
        assert user.email == 'test@example.com'
        assert user.is_verified is True

    def test_user_password_hashing(self, app, new_user):
        from models.user import User
        user = db.session.get(User, new_user.id)
        assert user.password_hash != 'password123'
        assert user.check_password('password123') is True
        assert user.check_password('wrongpass') is False

    def test_user_role_default(self, app, new_user):
        from models.user import User, UserRole
        user = db.session.get(User, new_user.id)
        assert user.role == UserRole.USER

    def test_user_money_default(self, app, new_user):
        from models.user import User
        user = db.session.get(User, new_user.id)
        assert user.money == 100
        assert user.health == 30000

    def test_user_repr(self, app, new_user):
        assert repr(new_user) == '<User testplayer>'


class TestGameModels:
    def test_create_location(self, app):
        from models.location import Location
        loc = Location(name='غزة', cost=100, cooldown=30)
        db.session.add(loc)
        db.session.commit()
        assert loc.id is not None
        assert loc.name == 'غزة'

    def test_create_item(self, app):
        from models.item import Item
        item = Item(name='مسدس', type='weapon', cost=500)
        db.session.add(item)
        db.session.commit()
        assert item.id is not None
        assert item.type == 'weapon'

    def test_create_crime(self, app):
        from models.gameplay import Crime
        crime = Crime(name='سرقة', min_level=1, energy_cost=10, cooldown=60, money_reward_min=100, money_reward_max=500)
        db.session.add(crime)
        db.session.commit()
        assert crime.id is not None
        assert crime.min_level == 1

    def test_create_gang(self, app, new_user):
        from models.social import Gang
        gang = Gang(name='الأسود', leader_id=new_user.id)
        db.session.add(gang)
        db.session.commit()
        assert gang.id is not None
        assert gang.leader_id == new_user.id


class TestHostessModel:
    def test_create_hostess(self, app):
        from models.hostess import Hostess
        hostess = Hostess(name='ليلى', role='companion', price=500, dialogue_style='friendly')
        db.session.add(hostess)
        db.session.commit()
        assert hostess.id is not None
        assert hostess.is_active is True
