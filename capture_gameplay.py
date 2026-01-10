import asyncio
from playwright.async_api import async_playwright
import datetime
import os
from run import app
from urllib.parse import urlencode, urlparse


def list_endpoints(base="http://localhost:8000"):
    with app.app_context():
        urls = []
        for rule in app.url_map.iter_rules():
            if ("GET" in rule.methods and
                    not rule.endpoint.startswith("static")):
                if "<" in rule.rule:
                    continue
                if rule.rule.strip("/") == "logout":
                    continue
                if (rule.rule.startswith("/@vite") or
                        rule.rule.startswith("/@react-refresh")):
                    continue
                url = base + rule.rule
                urls.append(url)
        # Add special cases that rely on query params or detail pages
        urls.extend([
            base + "/leaderboard?type=gang",
            base + "/leaderboard?type=rich",
            base + "/leaderboard?type=level",
            base + "/search?" + urlencode({"q": "Azad"}),
            base + "/news/1",
        ])
        # Dynamic examples for parameterized routes
        try:
            from models.social import Gang
            top_gang = Gang.query.order_by(Gang.level.desc()).first()
            if top_gang:
                urls.append(base + f"/gang/view/{top_gang.id}")
        except Exception:
            pass
        try:
            from models.forum import ForumTopic
            latest_topic = ForumTopic.query.order_by(
                ForumTopic.last_post_at.desc()).first()
            if latest_topic:
                urls.append(base + f"/forum/topic/{latest_topic.id}")
        except Exception:
            pass
        # De-duplicate and keep stable order
        seen = set()
        final = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                final.append(u)
        print(f"Total endpoints (GET, static-free, no params): {len(final)}")
        return final


def build_file_path_for_url(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path == "":
        path = "index"
    base_dir = os.path.join("static", "video", "endpoints", path)
    if parsed.query:
        q = parsed.query.replace("&", "__").replace("=", "_").replace("?", "_")
        file_path = os.path.join(base_dir, f"__{q}.png")
    else:
        file_path = base_dir + ".png"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    return file_path


async def capture_screenshots():
    # Ensure directory exists
    if not os.path.exists("static/video"):
        os.makedirs("static/video")

    async with async_playwright() as p:
        # --- Session 1: Logged In (Azad) ---
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720})
        page = await context.new_page()

        try:
            # Login
            print("Logging in...")
            try:
                await page.goto("http://localhost:8000/debug_login")
                await page.wait_for_url("**/hara", timeout=10000)
                print("Logged in via debug_login")
                logged_in = True
            except Exception:
                await page.goto("http://localhost:8000/login")
                logged_in = False

            # Try known Master password flows: dynamic, then fallback to 123456
            def today_master():
                now = datetime.datetime.now()
                return (f"Azad@1983@{now.strftime('%Y')}@"
                        f"{now.strftime('%m')}@{now.strftime('%d')}")
            if not logged_in:
                for candidate in (today_master(), "123456"):
                    await page.wait_for_selector(
                        'input[name="username"]', timeout=10000)
                    await page.fill('input[name="username"]', "Azad")
                    await page.wait_for_selector('#password', timeout=10000)
                    await page.fill('#password', candidate)
                    await page.wait_for_selector('.btn-auth', timeout=10000)
                    await page.click('.btn-auth')
                    try:
                        await page.wait_for_url("**/hara", timeout=15000)
                        print("Logged in successfully!")
                        break
                    except Exception:
                        print("Login attempt failed, trying fallback...")

            # Switch to Arabic
            print("Switching to Arabic...")
            await page.goto("http://localhost:8000/set_language/ar")
            await page.wait_for_timeout(1000)  # Wait for language switch

            # Dynamic list of endpoints from app.url_map
            # (Arabic session while logged-in)
            urls = list_endpoints()
            for idx, url in enumerate(urls, start=1):
                try:
                    file_path = build_file_path_for_url(url)
                    print(f"Capturing URL: {url} -> {file_path}")
                    if os.path.exists(file_path):
                        print("Already exists, skipping.")
                        continue
                    await page.goto(
                        url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(700)
                    await page.screenshot(path=file_path, full_page=True)
                except Exception as e:
                    print(f"Failed to capture {url}: {e}")

            await context.close()

        except Exception as e:
            print(f"Error in logged-in session: {e}")

        # --- Session 2: Logged Out (Public Pages) ---
        print("Starting public session...")
        context_public = await browser.new_context(
            viewport={'width': 1280, 'height': 720})
        page_public = await context_public.new_page()

        try:
            public_urls = [
                 ("http://localhost:8000/login",
                  "endpoint_public_login.png"),
                 ("http://localhost:8000/register",
                  "endpoint_public_register.png"),
                 ("http://localhost:8000/sitemap.xml",
                  "endpoint_public_sitemap_xml.png"),
                 ("http://localhost:8000/sitemap.xsl",
                  "endpoint_public_sitemap_xsl.png"),
            ]

            # Switch to Arabic
            await page_public.goto("http://localhost:8000/set_language/ar")
            await page_public.wait_for_timeout(500)

            for url, filename in public_urls:
                try:
                    print(f"Capturing {filename}...")
                    await page_public.goto(url, timeout=10000)
                    await page_public.wait_for_timeout(500)
                    await page_public.screenshot(
                        path=f"static/video/{filename}")
                except Exception as e:
                    print(f"Failed to capture {url}: {e}")

        except Exception as e:
            print(f"Error in public session: {e}")
        finally:
            await browser.close()
            print("Screenshots capture process finished.")

if __name__ == "__main__":
    asyncio.run(capture_screenshots())
