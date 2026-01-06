import requests
import sys

base_url = "http://127.0.0.1:8000"

def check_url(path):
    try:
        url = f"{base_url}{path}"
        response = requests.get(url)
        print(f"Checking {path}: {response.status_code}")
        if response.status_code == 200:
            if path == "/sitemap.xml":
                if "guide" in response.text:
                    print("SUCCESS: Guide link found in sitemap.xml")
                else:
                    print("FAILURE: Guide link NOT found in sitemap.xml")
            return True
        else:
            print(f"Error content: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"Failed to check {path}: {e}")
        return False

print("Starting SEO checks...")
checks = [
    "/robots.txt",
    "/sitemap.xml",
    "/guide"
]

all_passed = True
for path in checks:
    if not check_url(path):
        all_passed = False

if all_passed:
    print("All SEO checks passed!")
else:
    print("Some checks failed.")
    sys.exit(1)
