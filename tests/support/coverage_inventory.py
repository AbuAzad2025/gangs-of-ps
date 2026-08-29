"""Produce the project-wide quality coverage dashboard for backend, templates, JS, and E2E flows."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage.exceptions import NotPython
from coverage.parser import PythonParser

ROOT = Path(__file__).resolve().parents[2]

SCOPE_DIRS = ("routes", "services", "models", "utils", "forms", "admin")
SCOPE_FILES = ("factory.py", "extensions.py", "config.py")
SKIP_PARTS = {"/migrations/", "/tests/", "/scripts/", "/instance/", "/.venv/", "/venv/"}


def iter_scope_files() -> list[Path]:
    paths: list[Path] = []
    for name in SCOPE_DIRS:
        base = ROOT / name
        if base.is_dir():
            paths.extend(sorted(base.rglob("*.py")))
    for name in SCOPE_FILES:
        p = ROOT / name
        if p.is_file():
            paths.append(p)
    out: list[Path] = []
    for p in paths:
        s = p.as_posix()
        if any(part in s for part in SKIP_PARTS):
            continue
        if p.name in {"wsgi.py", "run.py"}:
            continue
        out.append(p)
    return sorted(set(out))


def static_statement_count(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
        parser = PythonParser(text=text, filename=str(path))
        parser.parse_source()
        return len(parser.statements)
    except (OSError, SyntaxError, ValueError, NotPython):
        return 0


def ensure_coverage_json(json_path: Path) -> Path:
    if json_path.is_file():
        return json_path

    coverage_db = ROOT / ".coverage"
    if coverage_db.is_file():
        try:
            import coverage

            cov = coverage.Coverage(data_file=str(coverage_db), config_file=str(ROOT / "pyproject.toml"))
            cov.load()
            cov.json_report(outfile=str(json_path))
        except Exception:
            pass
    return json_path


def load_measured(json_path: Path) -> dict[str, dict]:
    json_path = ensure_coverage_json(json_path)
    if not json_path.is_file():
        return {}
    data = json.loads(json_path.read_text(encoding="utf-8"))
    files = data.get("files") or {}
    measured: dict[str, dict] = {}
    for key, meta in files.items():
        rel = Path(key)
        if not rel.is_absolute():
            rel = (ROOT / rel).resolve()
        try:
            rel = rel.relative_to(ROOT)
        except ValueError:
            continue
        measured[rel.as_posix()] = meta
    return measured


def pct(meta: dict | None) -> float:
    if not meta:
        return 0.0
    summary = meta.get("summary") or {}
    if "percent_covered" in summary:
        return float(summary["percent_covered"])
    num = int(summary.get("num_statements") or 0)
    covered = int(summary.get("covered_lines") or 0)
    if num == 0:
        return 100.0
    return 100.0 * covered / num


def python_coverage_summary(json_path: Path) -> tuple[float, int, int, int]:
    measured = load_measured(json_path)
    rows: list[tuple[str, float, int, int]] = []
    total_stmts = 0
    total_covered = 0
    for path in iter_scope_files():
        rel = path.relative_to(ROOT).as_posix()
        meta = measured.get(rel)
        if meta:
            summary = meta.get("summary") or {}
            stmts = int(summary.get("num_statements") or 0)
            covered = int(summary.get("covered_lines") or 0)
        else:
            stmts = static_statement_count(path)
            covered = 0
        total_stmts += stmts
        total_covered += covered
        rows.append((rel, pct(meta), stmts, covered))
    total_pct = 100.0 if total_stmts == 0 else 100.0 * total_covered / total_stmts
    return total_pct, total_stmts, total_covered, len(rows)


def render_template_filters() -> dict[str, object]:
    def number_format(value):
        try:
            return "{:,}".format(value)
        except (TypeError, ValueError):
            return value

    def safe_message_html(value):
        if value is None:
            return ""
        value = str(value)
        if "<" not in value and ">" not in value:
            return value
        from bs4 import BeautifulSoup
        from markupsafe import Markup

        allowed_tags = {"a", "b", "br", "div", "em", "i", "li", "ol", "p", "small", "span", "strong", "ul"}
        soup = BeautifulSoup(value, "html.parser")
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()
        for tag in soup.find_all(True):
            if tag.name not in allowed_tags:
                tag.unwrap()
                continue
            if tag.name == "a":
                href = tag.get("href")
                title = tag.get("title")
                attrs = {}
                if href:
                    href = str(href)
                    if href.startswith(("http://", "https://", "/")):
                        attrs["href"] = href
                        attrs["rel"] = "nofollow noopener noreferrer"
                        attrs["target"] = "_blank"
                if title:
                    attrs["title"] = str(title)
                tag.attrs = attrs
            else:
                tag.attrs = {}
        return Markup(str(soup))

    return {"number_format": number_format, "safe_message_html": safe_message_html}


def template_validation_summary() -> tuple[float, int, int]:
    import jinja2

    template_dir = ROOT / "templates"
    templates = sorted(template_dir.rglob("*.html"))
    if not templates:
        return 0.0, 0, 0

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(template_dir)), autoescape=True)
    filters = render_template_filters()
    env.filters.update(filters)

    valid = 0
    for template_file in templates:
        relative = template_file.relative_to(template_dir).as_posix()
        try:
            env.get_template(relative)
            valid += 1
        except Exception:
            continue
    return (100.0 * valid / len(templates)), len(templates), valid


def frontend_js_summary() -> tuple[float, int, int]:
    js_dir = ROOT / "static" / "js"
    js_files = sorted(js_dir.glob("*.js"))
    if not js_files:
        return 0.0, 0, 0
    valid = 0
    for js_file in js_files:
        result = subprocess.run(["node", "--check", str(js_file)], capture_output=True, text=True)
        if result.returncode == 0:
            valid += 1
    return (100.0 * valid / len(js_files)), len(js_files), valid


def junit_summary(xml_paths: list[Path]) -> tuple[float, int, int, int]:
    total = 0
    passed = 0
    failed = 0
    skipped = 0
    for xml_path in xml_paths:
        if not xml_path.exists():
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue

        for case in root.iter("testcase"):
            total += 1
            if case.find("failure") is not None:
                failed += 1
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1

    if total == 0:
        return 0.0, 0, 0, 0
    pct = 100.0 * passed / total
    return pct, total, passed, failed


def load_browser_summary(json_path: Path | None) -> dict:
    if not json_path or not json_path.exists():
        return {
            "coverage_percent": 0.0,
            "total_bytes": 0,
            "executed_bytes": 0,
            "scripts": 0,
            "source": "playwright chromium js coverage",
        }

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "coverage_percent": 0.0,
            "total_bytes": 0,
            "executed_bytes": 0,
            "scripts": 0,
            "source": "playwright chromium js coverage",
        }

    return {
        "coverage_percent": float(payload.get("percent", 0.0)),
        "total_bytes": int(payload.get("total_bytes", 0)),
        "executed_bytes": int(payload.get("executed_bytes", 0)),
        "scripts": int(payload.get("scripts", 0)),
        "source": payload.get("source", "playwright chromium js coverage"),
    }


def build_dashboard(report_dir: Path, backend_json: Path, e2e_xml: list[Path], browser_json: Path | None = None) -> dict:
    backend_pct, backend_total, backend_covered, backend_files = python_coverage_summary(backend_json)
    template_pct, template_total, template_valid = template_validation_summary()
    js_pct, js_total, js_valid = frontend_js_summary()
    browser_pct = load_browser_summary(browser_json)
    e2e_pct, e2e_total, e2e_passed, e2e_failed = junit_summary(e2e_xml)

    overall_pct = (
        backend_pct + template_pct + js_pct + browser_pct["coverage_percent"] + e2e_pct
    ) / 5.0

    dashboard = {
        "backend": {
            "coverage_percent": round(backend_pct, 2),
            "total_statements": backend_total,
            "covered_statements": backend_covered,
            "files_in_scope": backend_files,
            "source": "pytest-cov",
        },
        "templates": {
            "coverage_percent": round(template_pct, 2),
            "total_templates": template_total,
            "valid_templates": template_valid,
            "source": "jinja2 compile validation",
        },
        "javascript": {
            "coverage_percent": round(js_pct, 2),
            "total_files": js_total,
            "valid_files": js_valid,
            "source": "node --check syntax validation",
        },
        "browser": {
            "coverage_percent": round(browser_pct["coverage_percent"], 2),
            "total_bytes": browser_pct["total_bytes"],
            "executed_bytes": browser_pct["executed_bytes"],
            "scripts": browser_pct["scripts"],
            "source": browser_pct["source"],
        },
        "e2e": {
            "coverage_percent": round(e2e_pct, 2),
            "total_tests": e2e_total,
            "passed_tests": e2e_passed,
            "failed_tests": e2e_failed,
            "source": "pytest junit xml",
        },
        "overall": {
            "quality_score_percent": round(overall_pct, 2),
        },
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "project-coverage-dashboard.json"
    json_path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")

    summary_lines = [
        "Gangs of Palestine — full project quality coverage dashboard",
        "",
        f"Backend Python coverage: {dashboard['backend']['coverage_percent']:.2f}% ({dashboard['backend']['covered_statements']}/{dashboard['backend']['total_statements']} statements covered)",
        f"Template validation: {dashboard['templates']['coverage_percent']:.2f}% ({dashboard['templates']['valid_templates']}/{dashboard['templates']['total_templates']} valid templates)",
        f"JavaScript validation: {dashboard['javascript']['coverage_percent']:.2f}% ({dashboard['javascript']['valid_files']}/{dashboard['javascript']['total_files']} valid files)",
        f"Browser JavaScript coverage: {dashboard['browser']['coverage_percent']:.2f}% ({dashboard['browser']['executed_bytes']}/{dashboard['browser']['total_bytes']} bytes executed)",
        f"E2E flow coverage: {dashboard['e2e']['coverage_percent']:.2f}% ({dashboard['e2e']['passed_tests']}/{dashboard['e2e']['total_tests']} tests passed)",
        f"Overall quality score: {dashboard['overall']['quality_score_percent']:.2f}%",
        "",
        "This report combines Python coverage, template integrity, JavaScript syntax validation, real browser coverage, and E2E smoke execution.",
    ]
    (report_dir / "project-coverage-dashboard.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    md_lines = [
        "# Gangs of Palestine — full project quality coverage dashboard",
        "",
        "## Executive summary",
        "",
        f"- Backend Python coverage: **{dashboard['backend']['coverage_percent']:.2f}%** ({dashboard['backend']['covered_statements']}/{dashboard['backend']['total_statements']} statements covered)",
        f"- Template validation: **{dashboard['templates']['coverage_percent']:.2f}%** ({dashboard['templates']['valid_templates']}/{dashboard['templates']['total_templates']} valid templates)",
        f"- JavaScript validation: **{dashboard['javascript']['coverage_percent']:.2f}%** ({dashboard['javascript']['valid_files']}/{dashboard['javascript']['total_files']} valid files)",
        f"- Browser JavaScript coverage: **{dashboard['browser']['coverage_percent']:.2f}%** ({dashboard['browser']['executed_bytes']}/{dashboard['browser']['total_bytes']} bytes executed)",
        f"- E2E flow coverage: **{dashboard['e2e']['coverage_percent']:.2f}%** ({dashboard['e2e']['passed_tests']}/{dashboard['e2e']['total_tests']} tests passed)",
        f"- Overall quality score: **{dashboard['overall']['quality_score_percent']:.2f}%**",
        "",
        "## Coverage sources",
        "",
        "| Layer | Source | Result |",
        "| --- | --- | --- |",
        f"| Backend | {dashboard['backend']['source']} | {dashboard['backend']['coverage_percent']:.2f}% |",
        f"| Templates | {dashboard['templates']['source']} | {dashboard['templates']['coverage_percent']:.2f}% |",
        f"| JavaScript | {dashboard['javascript']['source']} | {dashboard['javascript']['coverage_percent']:.2f}% |",
        f"| Browser | {dashboard['browser']['source']} | {dashboard['browser']['coverage_percent']:.2f}% |",
        f"| E2E | {dashboard['e2e']['source']} | {dashboard['e2e']['coverage_percent']:.2f}% |",
    ]
    (report_dir / "project-coverage-dashboard.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    html_rows = "\n".join(
        [
            "<tr>",
            f"<td>Backend</td><td>{dashboard['backend']['source']}</td><td>{dashboard['backend']['coverage_percent']:.2f}%</td><td>{dashboard['backend']['covered_statements']}/{dashboard['backend']['total_statements']}</td>",
            "</tr>",
            "<tr>",
            f"<td>Templates</td><td>{dashboard['templates']['source']}</td><td>{dashboard['templates']['coverage_percent']:.2f}%</td><td>{dashboard['templates']['valid_templates']}/{dashboard['templates']['total_templates']}</td>",
            "</tr>",
            "<tr>",
            f"<td>JavaScript</td><td>{dashboard['javascript']['source']}</td><td>{dashboard['javascript']['coverage_percent']:.2f}%</td><td>{dashboard['javascript']['valid_files']}/{dashboard['javascript']['total_files']}</td>",
            "</tr>",
            "<tr>",
            f"<td>Browser</td><td>{dashboard['browser']['source']}</td><td>{dashboard['browser']['coverage_percent']:.2f}%</td><td>{dashboard['browser']['executed_bytes']}/{dashboard['browser']['total_bytes']}</td>",
            "</tr>",
            "<tr>",
            f"<td>E2E</td><td>{dashboard['e2e']['source']}</td><td>{dashboard['e2e']['coverage_percent']:.2f}%</td><td>{dashboard['e2e']['passed_tests']}/{dashboard['e2e']['total_tests']}</td>",
            "</tr>",
        ]
    )
    html_doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Gangs of Palestine Coverage Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; background: #f8fafc; }}
    h1, h2 {{ color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1000px; background: white; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.75rem; text-align: left; }}
    th {{ background: #e5e7eb; }}
    .summary {{ margin: 1rem 0 2rem; padding: 1rem; background: white; border: 1px solid #e5e7eb; max-width: 1000px; }}
  </style>
</head>
<body>
  <h1>Gangs of Palestine — full project quality coverage dashboard</h1>
  <div class=\"summary\">
    <p><strong>Overall quality score:</strong> {dashboard['overall']['quality_score_percent']:.2f}%</p>
    <p><strong>Backend Python coverage:</strong> {dashboard['backend']['coverage_percent']:.2f}%</p>
    <p><strong>Template validation:</strong> {dashboard['templates']['coverage_percent']:.2f}%</p>
    <p><strong>JavaScript validation:</strong> {dashboard['javascript']['coverage_percent']:.2f}%</p>
    <p><strong>Browser JS coverage:</strong> {dashboard['browser']['coverage_percent']:.2f}%</p>
    <p><strong>E2E flow coverage:</strong> {dashboard['e2e']['coverage_percent']:.2f}%</p>
  </div>
  <h2>Layer summary</h2>
  <table>
    <thead>
      <tr><th>Layer</th><th>Source</th><th>Coverage</th><th>Counts</th></tr>
    </thead>
    <tbody>
      {html_rows}
    </tbody>
  </table>
</body>
</html>
"""
    (report_dir / "project-coverage-dashboard.html").write_text(html_doc, encoding="utf-8")
    return dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-json", type=Path, default=ROOT / "coverage" / "unit-coverage.json")
    parser.add_argument("--browser-json", type=Path, default=None)
    parser.add_argument("--e2e-xml", nargs="*", type=Path, default=[ROOT / "test-results" / "e2e-junit.xml"])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "coverage")
    args = parser.parse_args()

    if not args.backend_json.exists():
        fallback = ROOT / "coverage.json"
        if fallback.exists():
            args.backend_json = fallback
        else:
            args.backend_json = ROOT / "coverage" / "unit-coverage.json"

    if args.browser_json is None:
        default_browser = ROOT / "coverage" / "browser-coverage.json"
        if default_browser.exists():
            args.browser_json = default_browser

    dashboard = build_dashboard(args.output_dir, args.backend_json, args.e2e_xml, args.browser_json)
    sys.stdout.write(json.dumps(dashboard, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
