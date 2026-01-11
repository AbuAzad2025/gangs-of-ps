import os
import re
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse, urlunparse


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")


class _AttrCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if not v:
                continue
            if k in ("href", "src"):
                self.urls.append(v)


@dataclass
class CheckReport:
    missing_endpoints: list
    missing_static: list
    crawl_404: list
    crawl_5xx: list
    crawl_other_bad: list
    visited: int


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _iter_files(root_dir, exts):
    for base, _, files in os.walk(root_dir):
        for fn in files:
            if any(fn.lower().endswith(ext) for ext in exts):
                yield os.path.join(base, fn)


def _collect_template_url_for_endpoints():
    rx = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
    endpoints = set()
    for path in _iter_files(TEMPLATES_DIR, [".html"]):
        txt = _read_text(path)
        for m in rx.finditer(txt):
            endpoints.add(m.group(1))
    return endpoints


def _collect_template_static_files():
    found = set()
    rx1 = re.compile(
        r"url_for\(\s*['\"]static['\"].*?filename\s*=\s*['\"]([^'\"]+)['\"]",
        re.DOTALL,
    )
    rx2 = re.compile(r"(?:href|src)\s*=\s*['\"]/static/([^'\"?#]+)")
    for path in _iter_files(TEMPLATES_DIR, [".html"]):
        txt = _read_text(path)
        for m in rx1.finditer(txt):
            found.add(m.group(1))
        for m in rx2.finditer(txt):
            found.add(m.group(1))
    return found


def _collect_css_static_urls():
    found = set()
    rx = re.compile(r"url\(\s*['\"]?(/static/[^'\"\)]+)['\"]?\s*\)")
    for path in _iter_files(os.path.join(STATIC_DIR, "css"), [".css"]):
        txt = _read_text(path)
        for m in rx.finditer(txt):
            p = m.group(1)
            if p.startswith("/static/"):
                found.add(p[len("/static/") :])
    return found


def _static_exists(rel_path):
    if not rel_path:
        return True
    rel_path = rel_path.lstrip("/\\")
    full = os.path.join(STATIC_DIR, rel_path)
    return os.path.exists(full)


def _normalize_url(u):
    p = urlparse(u)
    p = p._replace(fragment="")
    return urlunparse(p)


def _is_internal_path(u):
    if not u:
        return False
    if u.startswith("//"):
        return False
    if u.startswith("http://") or u.startswith("https://"):
        return False
    if u.startswith("mailto:") or u.startswith("tel:") or u.startswith("javascript:"):
        return False
    if u.startswith("#"):
        return False
    return u.startswith("/")


def _seed_urls(app):
    seeds = set()
    seeds.update(
        [
            "/",
            "/hara",
            "/garage",
            "/dealership",
            "/market",
            "/casino",
            "/casino/blackjack",
            "/casino/racing",
            "/forum",
            "/travel",
            "/inventory",
            "/developer",
            "/admin/",
        ]
    )

    for rule in app.url_map.iter_rules():
        if "GET" not in (rule.methods or set()):
            continue
        path = str(rule.rule)
        if "<" in path or ">" in path:
            continue
        if not path.startswith("/"):
            continue
        if path.startswith("/static/"):
            continue
        if path.startswith("/login") or path.startswith("/logout"):
            continue
        seeds.add(path)

    with app.app_context():
        try:
            from models import User

            u = User.query.order_by(User.id.asc()).first()
            if u:
                seeds.add(f"/profile/{u.id}")
        except Exception:
            pass

        try:
            from models import MarketAsset

            a = MarketAsset.query.order_by(MarketAsset.id.asc()).first()
            if a:
                seeds.add(f"/market/trade/{a.id}?tab=spot")
        except Exception:
            pass

        try:
            from models import ForumTopic

            t = ForumTopic.query.order_by(ForumTopic.id.desc()).first()
            if t:
                seeds.add(f"/forum/topic/{t.id}")
        except Exception:
            pass

    return [u for u in seeds if u]


def run_full_check(max_pages=800):
    sys.path.insert(0, PROJECT_ROOT)
    from factory import create_app

    app = create_app()
    app.config.update(TESTING=True)
    app.config.setdefault("RATELIMIT_ENABLED", False)

    endpoints_in_templates = _collect_template_url_for_endpoints()
    static_in_templates = _collect_template_static_files()
    static_in_css = _collect_css_static_urls()

    existing_endpoints = set(app.view_functions.keys())
    missing_endpoints = sorted(
        e
        for e in endpoints_in_templates
        if e not in existing_endpoints and e != "static"
    )

    missing_static = sorted(
        p for p in (static_in_templates | static_in_css) if not _static_exists(p)
    )

    client = app.test_client()
    now = datetime.now()
    master = f"Azad@1983@{now:%Y}@{now:%m}@{now:%d}"
    client.post(
        "/login",
        data={"username": "Azad", "password": master},
        follow_redirects=True,
    )

    queue = deque(_seed_urls(app))
    seen = set()
    crawl_404 = []
    crawl_5xx = []
    crawl_other_bad = []
    visited = 0

    while queue and visited < max_pages:
        url = _normalize_url(queue.popleft())
        if not url or url in seen:
            continue
        seen.add(url)
        visited += 1

        resp = client.get(url, follow_redirects=False)
        status = resp.status_code
        if status == 404:
            if url.startswith("/admin/") and "/ajax/lookup/" in url:
                continue
            crawl_404.append(url)
            continue
        if status >= 500:
            crawl_5xx.append(url)
            continue
        if status == 405:
            continue
        if status in (401, 403):
            continue
        if status in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location")
            if loc and _is_internal_path(loc):
                if loc.startswith("/login"):
                    continue
                queue.append(loc)
            continue
        if status >= 400:
            if url.startswith("/admin/") and "/ajax/lookup/" in url and status in (400, 404):
                continue
            crawl_other_bad.append((url, status))
            continue

        ct = resp.headers.get("Content-Type", "")
        if "text/html" not in ct:
            continue

        html = resp.get_data()
        if isinstance(html, (bytes, bytearray)):
            html = html.decode("utf-8", "ignore")
        parser = _AttrCollector()
        try:
            parser.feed(html)
        except Exception:
            parser.urls = re.findall(r"(?:href|src|action)\s*=\s*['\"]([^'\"]+)['\"]", html)

        for raw in parser.urls:
            if not raw:
                continue
            raw = raw.strip()
            if raw.startswith("/static/"):
                continue
            if raw.startswith("/login"):
                continue
            if _is_internal_path(raw):
                queue.append(raw)

    return CheckReport(
        missing_endpoints=missing_endpoints,
        missing_static=missing_static,
        crawl_404=sorted(set(crawl_404)),
        crawl_5xx=sorted(set(crawl_5xx)),
        crawl_other_bad=sorted(set(crawl_other_bad)),
        visited=visited,
    )


def main():
    report = run_full_check()
    print("FULL_CHECK_REPORT")
    print("visited_pages", report.visited)
    print("missing_endpoints", len(report.missing_endpoints))
    for e in report.missing_endpoints[:200]:
        print("  -", e)
    print("missing_static", len(report.missing_static))
    for p in report.missing_static[:200]:
        print("  -", p)
    print("crawl_404", len(report.crawl_404))
    for u in report.crawl_404[:200]:
        print("  -", u)
    print("crawl_5xx", len(report.crawl_5xx))
    for u in report.crawl_5xx[:200]:
        print("  -", u)
    print("crawl_other_bad", len(report.crawl_other_bad))
    for u, s in report.crawl_other_bad[:200]:
        print("  -", s, u)

    failed = (
        report.missing_endpoints
        or report.missing_static
        or report.crawl_5xx
        or report.crawl_other_bad
    )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
