from __future__ import annotations

from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import pytest

from config import Config
from extensions import db
from factory import create_app


class _LocalTestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


@pytest.fixture()
def app():
    app = create_app(_LocalTestConfig)
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_robots_txt_served(client):
    res = client.get("/robots.txt")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "User-agent:" in body
    assert "Sitemap:" in body


def test_sitemap_xml_links_are_crawlable_for_guest(client):
    res = client.get("/sitemap.xml")
    assert res.status_code == 200

    root = ET.fromstring(res.get_data(as_text=True))
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [node.text for node in root.findall("s:url/s:loc", ns) if node.text]
    assert locs

    for loc in locs:
        parsed = urlparse(loc)
        path_qs = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        page_res = client.get(path_qs, follow_redirects=False)
        assert page_res.status_code < 400

        if page_res.status_code in (301, 302, 303, 307, 308):
            to = (page_res.headers.get("Location") or "").lower()
            assert not to.startswith("/login")
            assert not to.startswith("/register")
