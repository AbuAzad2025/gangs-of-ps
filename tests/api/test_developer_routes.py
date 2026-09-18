from models.system import SystemConfig
from models.user import User


class TestDeveloperRoutes:
    def test_developer_dashboard_requires_developer(self, logged_in_client):
        response = logged_in_client.get('/developer', follow_redirects=False)
        assert response.status_code == 302

    def test_developer_can_verify_and_update_maintenance(
            self, client, developer_user, login_as):
        login_as(developer_user)

        verify = client.post(
            '/developer/verify',
            data={'password': 'password123'},
            follow_redirects=False,
        )
        assert verify.status_code == 302

        response = client.post(
            '/developer/maintenance',
            data={'mode': 'on', 'message': 'Scheduled maintenance'},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert SystemConfig.get_value('maintenance_mode') == 'true'
        assert SystemConfig.get_value('maintenance_message') == 'Scheduled maintenance'

    def test_developer_updates_world_event_and_game_settings(
            self, client, db, developer_user, login_as):
        login_as(developer_user)
        verified = client.post(
            '/developer/verify',
            data={'password': 'password123'},
            follow_redirects=False,
        )
        assert verified.status_code == 302

        season = client.post(
            '/developer/world-season',
            data={
                'world_event_active': 'on',
                'world_event_title': 'Test event',
                'world_event_description': 'A tested event',
                'world_event_money_bonus_pct': '15',
                'world_event_ends_at': '2030-01-01',
                'current_season_name': 'Season test',
                'season_ends_at': '2030-02-01',
            },
            follow_redirects=False,
        )
        assert season.status_code == 302
        assert SystemConfig.get_value('world_event_active') == 'true'
        assert SystemConfig.get_value('world_event_title') == 'Test event'
        assert SystemConfig.get_value('world_event_money_bonus_pct') == '15'
        assert SystemConfig.get_value('current_season_name') == 'Season test'

        settings = client.post(
            '/developer/entertainment/update',
            data={
                'entertainment_enabled': 'true',
                'betting_enabled': 'true',
                'allowed_currencies': 'diamonds',
                'house_cut_percent': '25',
                'betting_min_stake': '10',
                'betting_max_stake': '500',
                'game_chess_enabled': 'true',
                'game_trix_enabled': 'false',
                'game_tarneeb_enabled': 'true',
            },
            follow_redirects=False,
        )
        assert settings.status_code == 302
        assert SystemConfig.get_value('betting_allowed_currencies') == 'diamonds'
        assert SystemConfig.get_value('betting_min_stake') == '10'
        assert SystemConfig.get_value('game_trix_enabled') == 'false'

    def test_developer_user_lifecycle_disables_kills_and_resurrects(
            self, client, db, developer_user, login_as):
        from tests.support.factories import make_user

        target = make_user(db, username='managed-player', money=100)
        target_id = int(target.__dict__['id'])
        login_as(developer_user)
        client.post(
            '/developer/verify',
            data={'password': 'password123'},
            follow_redirects=False,
        )

        disabled = client.post(
            f'/developer/user/disable/{target_id}',
            follow_redirects=False,
        )
        assert disabled.status_code == 302
        db.session.expire_all()
        assert db.session.get(User, target_id).banned_until is not None

        enabled = client.post(
            f'/developer/user/enable/{target_id}',
            follow_redirects=False,
        )
        assert enabled.status_code == 302
        db.session.expire_all()
        assert db.session.get(User, target_id).banned_until is None

        killed = client.post(
            f'/developer/user/kill/{target_id}',
            follow_redirects=False,
        )
        assert killed.status_code == 302
        db.session.expire_all()
        dead = db.session.get(User, target_id)
        assert dead.health == 0
        assert dead.hospital_until is not None

        resurrected = client.post(
            f'/developer/user/resurrect/{target_id}',
            follow_redirects=False,
        )
        assert resurrected.status_code == 302
        db.session.expire_all()
        alive = db.session.get(User, target_id)
        assert alive.health == alive.max_health
        assert alive.hospital_until is None

    def test_developer_user_search_and_self_delete_are_safe(
            self, client, db, developer_user, login_as):
        developer_id = int(developer_user.__dict__['id'])
        login_as(developer_user)
        listing = client.get('/developer/users?q=devtest')
        assert listing.status_code == 200
        assert b'devtest' in listing.data

        response = client.post(
            f'/developer/user/delete/{developer_id}',
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert db.session.get(User, developer_id) is not None
