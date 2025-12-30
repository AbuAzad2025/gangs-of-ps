import os
import re
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from factory import create_app


IGNORE_PATH_PREFIXES = (
    "/static/",
    "/favicon.ico",
)


IGNORE_FILE_SUBSTRINGS = (
    os.path.join("static", "adminlte"),
    os.path.join("static", "avatars"),
    os.path.join("static", "cars"),
    os.path.join("static", "crimes"),
    os.path.join("static", "images"),
    os.path.join("static", "img"),
    os.path.join("static", "items"),
    os.path.join("static", "locations"),
    os.path.join("static", "properties"),
    os.path.join("static", "videos"),
    os.path.join("static", "weapons"),
)


ATTR_PATTERNS = [
    re.compile(r"""href\s*=\s*["'](?P<path>/[^"']+)["']""", re.IGNORECASE),
    re.compile(r"""action\s*=\s*["'](?P<path>/[^"']+)["']""", re.IGNORECASE),
    re.compile(r"""src\s*=\s*["'](?P<path>/[^"']+)["']""", re.IGNORECASE),
]


JS_PATTERNS = [
    re.compile(r"""fetch\(\s*["'](?P<path>/[^"']+)["']"""),
    re.compile(r"""\$\.(?:get|post)\(\s*["'](?P<path>/[^"']+)["']"""),
    re.compile(r"""axios\.(?:get|post|put|delete)\(\s*["'](?P<path>/[^"']+)["']"""),
    re.compile(r"""location(?:\.href)?\s*=\s*["'](?P<path>/[^"']+)["']"""),
]


def _normalize_path(raw):
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("//"):
        return None
    if raw.startswith("/static/"):
        return None
    if raw.startswith("/api/"):
        return raw.split("?", 1)[0].split("#", 1)[0]
    p = raw.split("?", 1)[0].split("#", 1)[0]
    if not p.startswith("/"):
        return None
    for pref in IGNORE_PATH_PREFIXES:
        if p.startswith(pref):
            return None
    return p


def _rule_to_regex(rule_str):
    s = rule_str
    s = re.sub(r"<[^>]+>", r"[^/]+", s)
    if not s.startswith("^"):
        s = "^" + s
    if not s.endswith("$"):
        s = s + "$"
    return re.compile(s)


def _collect_rules(app):
    regexes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("static"):
            continue
        regexes.append(_rule_to_regex(str(rule)))
    return regexes


def _matches_any_rule(path, rule_regexes):
    if any(rx.match(path) for rx in rule_regexes):
        return True
    if not path.endswith("/"):
        path2 = path + "/"
        return any(rx.match(path2) for rx in rule_regexes)
    return False


def _should_ignore_file(path):
    p = os.path.normpath(path)
    return any(sub in p for sub in IGNORE_FILE_SUBSTRINGS)


def _extract_paths_from_text(text, patterns):
    out = set()
    for pat in patterns:
        for m in pat.finditer(text):
            raw = m.group("path")
            norm = _normalize_path(raw)
            if norm:
                out.add(norm)
    return out


def _walk_files(root_dir, exts):
    for base, _, files in os.walk(root_dir):
        for fn in files:
            if not any(fn.lower().endswith(ext) for ext in exts):
                continue
            full = os.path.join(base, fn)
            if _should_ignore_file(full):
                continue
            yield full


def audit():
    app = create_app()
    rules = _collect_rules(app)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    templates_dir = os.path.join(repo_root, "templates")
    static_dir = os.path.join(repo_root, "static")

    found = set()

    for fp in _walk_files(templates_dir, exts=(".html",)):
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        found |= _extract_paths_from_text(text, ATTR_PATTERNS)
        found |= _extract_paths_from_text(text, JS_PATTERNS)

    for fp in _walk_files(static_dir, exts=(".js",)):
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        found |= _extract_paths_from_text(text, JS_PATTERNS)

    unknown = []
    for p in sorted(found):
        if p.startswith("/api/"):
            continue
        if not _matches_any_rule(p, rules):
            unknown.append(p)

    print("=== UI Link Audit ===")
    print(f"Found paths: {len(found)}")
    print(f"Unknown paths: {len(unknown)}")
    for p in unknown[:200]:
        print("❌", p)

    return 0 if not unknown else 1


if __name__ == "__main__":
    sys.exit(audit())

