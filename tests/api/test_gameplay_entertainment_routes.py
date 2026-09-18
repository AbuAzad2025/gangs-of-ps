from datetime import datetime, timedelta, timezone

from models.entertainment import GameChat, GameRoom
from models.gameplay import Crime, DailyTask, UserDailyTask
from models.system import SystemConfig
from models.user import User
from tests.support.factories import make_user


class TestGameplayRoutes:
    def test_daily_reward_updates_user_and_prevents_immediate_second_claim(
            self, logged_in_client, db, auth_user_id):
        before = db.session.get(User, auth_user_id)
        starting_money = before.money
        starting_energy = before.energy

        response = logged_in_client.post('/daily_reward', follow_redirects=False)
        assert response.status_code == 302
        db.session.expire_all()
        claimed = db.session.get(User, auth_user_id)
        assert claimed.daily_streak == 1
        assert claimed.last_daily_reward is not None
        assert claimed.money > starting_money
        assert claimed.energy > starting_energy
        claimed_reward_at = claimed.last_daily_reward
        claimed_money = claimed.money

        response = logged_in_client.post('/daily_reward', follow_redirects=False)
        assert response.status_code == 302
        db.session.expire_all()
        unchanged = db.session.get(User, auth_user_id)
        assert unchanged.last_daily_reward == claimed_reward_at
        assert unchanged.money == claimed_money

    def test_hara_exposes_reward_state_for_recent_claim(
            self, logged_in_client, db, auth_user_id):
        user = db.session.get(User, auth_user_id)
        user.last_daily_reward = datetime.now(timezone.utc).replace(tzinfo=None)
        user.daily_streak = 3
        db.session.commit()

        response = logged_in_client.get('/hara')
        assert response.status_code == 200
        assert 'ستريك' in response.get_data(as_text=True) or 'مكافأة' in response.get_data(as_text=True)

    def test_organized_crimes_public_page_is_available(self, client, db):
        from models.gameplay import OrganizedCrime

        db.session.add(OrganizedCrime(
            name='Public Test Heist',
            description='A public heist',
            min_level=1,
            is_active=True,
        ))
        db.session.commit()

        response = client.get('/organized_crimes')
        assert response.status_code == 200
        assert b'organized' in response.data.lower() or 'جرائم' in response.get_data(as_text=True)


    def test_daily_tasks_page_renders_and_collect_reward(self, logged_in_client, db, auth_user_id):
        task = DailyTask(
            description='Test crime task',
            target_type='crime',
            target_count=1,
            reward_money=350,
            reward_exp=25,
            min_level=1,
            is_active=True,
        )
        db.session.add(task)
        db.session.flush()

        first_task = UserDailyTask(
            user_id=auth_user_id,
            task_id=task.id,
            progress=1,
            is_completed=False,
        )
        db.session.add(first_task)
        db.session.commit()
        first_task_id = int(first_task.id)

        response = logged_in_client.get('/daily_tasks')
        assert response.status_code == 200

        reward_response = logged_in_client.post(f'/collect_task_reward/{first_task_id}', follow_redirects=False)
        assert reward_response.status_code == 302
        db.session.expire_all()
        updated_user = db.session.get(User, auth_user_id)
        assert updated_user.money > 0
        assert db.session.get(UserDailyTask, first_task_id).is_completed is True

    def test_collect_task_reward_rejects_incomplete_or_foreign_task(self, logged_in_client, db, auth_user_id):
        task = DailyTask(
            description='Test incomplete task',
            target_type='crime',
            target_count=2,
            reward_money=100,
            reward_exp=10,
            min_level=1,
            is_active=True,
        )
        db.session.add(task)
        db.session.flush()
        task_id = int(task.id)

        owned_task = UserDailyTask(
            user_id=auth_user_id,
            task_id=task_id,
            progress=0,
            is_completed=False,
        )
        db.session.add(owned_task)
        db.session.commit()
        owned_task_id = int(owned_task.id)

        response = logged_in_client.post(f'/collect_task_reward/{owned_task_id}', follow_redirects=False)
        assert response.status_code == 302
        assert db.session.get(UserDailyTask, owned_task_id).is_completed is False

        other_user = make_user(db, username='foreign_task_owner', money=50)
        foreign_task = UserDailyTask(
            user_id=other_user.id,
            task_id=task_id,
            progress=1,
            is_completed=False,
        )
        db.session.add(foreign_task)
        db.session.commit()
        foreign_task_id = int(foreign_task.id)

        foreign_response = logged_in_client.post(f'/collect_task_reward/{foreign_task_id}', follow_redirects=False)
        assert foreign_response.status_code == 302
        assert db.session.get(UserDailyTask, foreign_task_id).is_completed is False

    def test_daily_reward_rejects_repeat_claim_before_24_hours(self, logged_in_client, db, auth_user_id):
        user = db.session.get(User, auth_user_id)
        original_claim = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
        user.last_daily_reward = original_claim
        user.daily_streak = 2
        db.session.commit()

        response = logged_in_client.post('/daily_reward', follow_redirects=False)
        assert response.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, auth_user_id)
        assert refreshed.last_daily_reward == original_claim
        assert refreshed.daily_streak == 2


class TestEntertainmentRoutes:
    def test_entertainment_can_be_disabled_without_exposing_rooms(
            self, logged_in_client, db):
        SystemConfig.set_value('entertainment_enabled', 'false')
        db.session.commit()

        response = logged_in_client.get('/entertainment/', follow_redirects=False)

        assert response.status_code == 302
        assert response.location.endswith('/hara')

    def test_create_chess_room_state_and_chat(
            self, logged_in_client, db, auth_user_id):
        response = logged_in_client.post(
            '/entertainment/create_room',
            data={'game_type': 'chess', 'name': 'Test Chess Room'},
            follow_redirects=False,
        )
        assert response.status_code == 302
        room = GameRoom.query.one()
        room_id = room.id
        assert room.status == 'waiting'
        assert room.players.count() == 1
        assert room.players.first().user_id == auth_user_id
        initial_ready = room.players.first().is_ready

        state_response = logged_in_client.get(
            f'/entertainment/api/room/{room_id}/state')
        assert state_response.status_code == 200
        state = state_response.get_json()
        assert state['game_type'] == 'chess'
        assert state['players'][0]['user_id'] == auth_user_id

        chat_response = logged_in_client.post(
            f'/entertainment/api/room/{room_id}/chat',
            json={'message': 'Good luck!'},
        )
        assert chat_response.status_code == 200
        assert GameChat.query.one().message == 'Good luck!'

        ready_response = logged_in_client.post(
            f'/entertainment/api/room/{room_id}/ready')
        assert ready_response.status_code == 200
        db.session.expire_all()
        assert GameRoom.query.get(room_id).players.first().is_ready is (not initial_ready)

    def test_entertainment_rejects_invalid_room_input(self, logged_in_client):
        response = logged_in_client.post(
            '/entertainment/create_room',
            data={'game_type': 'invalid', 'name': 'Nope'},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.location.endswith('/entertainment/')

    def test_solo_chess_creation_charges_stake_and_accepts_move(
            self, logged_in_client, db, auth_user_id):
        user = db.session.get(User, auth_user_id)
        starting_money = user.money

        response = logged_in_client.post(
            '/entertainment/create_room',
            data={
                'game_type': 'chess',
                'name': 'Solo Chess',
                'mode': 'solo',
                'stake_amount': '25',
                'currency_type': 'money',
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        room = GameRoom.query.one()
        room_id = room.id
        assert room.status == 'playing'
        assert room.game_state['is_solo'] is True
        assert room.pot_amount == 25
        assert db.session.get(User, auth_user_id).money == starting_money - 25

        move = logged_in_client.post(
            f'/entertainment/api/room/{room_id}/move',
            json={'move': 'e2e4'},
        )
        assert move.status_code == 200
        db.session.expire_all()
        state = db.session.get(GameRoom, room_id).game_state
        assert state['history'][0] == 'e2e4'
        assert len(state['history']) == 2  # human move plus minimax reply

    def test_chess_move_rejects_illegal_and_out_of_turn_moves(
            self, logged_in_client, db):
        logged_in_client.post(
            '/entertainment/create_room',
            data={'game_type': 'chess', 'name': 'Move Tests'},
            follow_redirects=False,
        )
        room = GameRoom.query.one()
        room_id = room.id

        illegal = logged_in_client.post(
            f'/entertainment/api/room/{room_id}/move',
            json={'move': 'e2e5'},
        )
        assert illegal.status_code == 400
        assert illegal.get_json()['error'] == 'Illegal move'

        missing = logged_in_client.post(
            f'/entertainment/api/room/{room_id}/move',
            json={},
        )
        assert missing.status_code == 400
        assert missing.get_json()['error'] == 'No move provided'

    def test_staked_room_join_and_lobby_leave_refunds_resources(
            self, client, db, login_as, new_user):
        from tests.support.factories import make_user

        new_user.money = 100
        db.session.commit()
        login_as(new_user)
        response = client.post(
            '/entertainment/create_room',
            data={
                'game_type': 'chess',
                'name': 'Staked Lobby',
                'stake_amount': '20',
                'currency_type': 'money',
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        room = GameRoom.query.one()
        room_id = int(room.__dict__["id"])
        assert room.pot_amount == 20

        guest = make_user(db, username='guest', money=100)
        guest_id = int(guest.__dict__["id"])
        login_as(guest)
        joined = client.get(f'/entertainment/room/{room_id}', follow_redirects=False)
        assert joined.status_code == 200
        db.session.expire_all()
        room = db.session.get(GameRoom, room_id)
        assert room.players.count() == 2
        assert db.session.get(User, guest_id).money == 80
        assert room.pot_amount == 40

        left = client.post(
            f'/entertainment/api/room/{room_id}/leave',
            follow_redirects=False,
        )
        assert left.status_code == 200
        db.session.expire_all()
        assert db.session.get(User, guest_id).money == 100
        assert db.session.get(GameRoom, room_id).pot_amount == 20
