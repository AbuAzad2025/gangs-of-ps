"""HTTP client helpers for authenticated scenario tests."""
from __future__ import annotations

from models.user import User


def login_client(client, app, user: User, password: str = 'password123'):
    """Establish a logged-in session on the test client."""
    user_id = int(user.id)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return client
