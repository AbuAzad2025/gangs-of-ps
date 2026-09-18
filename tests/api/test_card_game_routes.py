from datetime import datetime, timedelta

from models.entertainment import GameRoom
from models.user import User
from tests.support.factories import make_user


def test_create_solo_trix_persists_playable_state(logged_in_client, db, auth_user_id):
    response = logged_in_client.post('/entertainment/create_room', data={
        'game_type': 'trix',
        'name': 'Trix room',
        'mode': 'solo',
    })
    assert response.status_code == 302
    room = GameRoom.query.filter_by(game_type='trix').one()
    assert room.status == 'playing'
    assert room.game_state['phase'] == 'choose_contract'
    assert sum(len(hand) for hand in room.game_state['hands'].values()) == 52
    assert room.players.count() == 1
    assert room.players.first().user_id == auth_user_id

    state_response = logged_in_client.get(
        f'/entertainment/api/room/{room.id}/state')
    assert state_response.status_code == 200
    assert state_response.get_json()['game_state']['phase'] in (
        'choose_contract', 'doubling', 'playing')


def test_create_solo_tarneeb_and_reject_invalid_room_data(logged_in_client, db):
    invalid = logged_in_client.post('/entertainment/create_room', data={
        'game_type': 'not-a-game',
        'name': 'Bad room',
    })
    assert invalid.status_code == 302
    assert GameRoom.query.count() == 0

    response = logged_in_client.post('/entertainment/create_room', data={
        'game_type': 'tarneeb',
        'name': 'Tarneeb room',
        'mode': 'solo',
    })
    assert response.status_code == 302
    room = GameRoom.query.filter_by(game_type='tarneeb').one()
    assert room.status == 'playing'
    assert room.game_state['phase'] == 'bidding'
    assert [len(hand) for hand in room.game_state['hands']] == [13] * 4


def test_combat_search_and_attack_guards(logged_in_client, db, auth_user_id):
    target = make_user(db, username='search-target', created_at=None)
    response = logged_in_client.get('/combat/?q=search-target')
    assert response.status_code == 200
    assert b'search-target' in response.data

    self_attack = logged_in_client.post(f'/combat/attack/{auth_user_id}')
    assert self_attack.status_code == 302
    assert self_attack.location.endswith('/combat/')

    target.health = 100
    db.session.commit()
    missing = logged_in_client.post('/combat/attack/999999')
    assert missing.status_code == 404


def test_combat_rejects_attacker_statuses(logged_in_client, db, auth_user_id):
    target = make_user(db, username='status-target')
    attacker = db.session.get(User, auth_user_id)

    attacker.jail_until = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    assert logged_in_client.post(f'/combat/attack/{target.id}').location.endswith('/jail/')


def test_combat_rejects_newbie_protected_targets(
        logged_in_client, db, auth_user_id):
    target = make_user(db, username='protected-target')
    attacker = db.session.get(User, auth_user_id)
    attacker.health = 30000
    target.created_at = datetime.utcnow()
    db.session.commit()
    protected = logged_in_client.post(f'/combat/attack/{target.id}')
    assert protected.status_code == 302
    assert protected.location.endswith('/combat/')
