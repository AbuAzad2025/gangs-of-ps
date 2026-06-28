"""Merge coverage.json with every in-scope game .py file (0% if never imported)."""
from __future__ import annotations

import json
import sys
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
        if p.name == "wsgi.py" or p.name == "run.py":
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


def load_measured(json_path: Path) -> dict[str, dict]:
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


def main() -> int:
    json_path = ROOT / "coverage.json"
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
    width = max((len(r[0]) for r in rows), default=20)

    lines = [
        "Gangs of Palestine — full Python coverage inventory",
        f"Scope: {', '.join(SCOPE_DIRS)} + {', '.join(SCOPE_FILES)}",
        f"Files: {len(rows)} | Total statements: {total_stmts} | Covered: {total_covered} | Total: {total_pct:.1f}%",
        "",
        f"{'FILE'.ljust(width)}  COV%   STMTS  COVERED",
        "-" * (width + 22),
    ]
    for rel, p, stmts, covered in rows:
        flag = " !" if p < 100.0 else "  "
        lines.append(f"{rel.ljust(width)}  {p:5.1f}  {stmts:5d}  {covered:7d}{flag}")

    unmeasured = sum(1 for rel, p, stmts, covered in rows if measured.get(rel) is None and stmts > 0)
    below_100 = sum(1 for _, p, stmts, _ in rows if stmts > 0 and p < 100.0)
    lines.extend([
        "",
        f"Summary: {below_100} files below 100% | {unmeasured} files never imported during test run",
        "Legend: ! = below 100% coverage target",
    ])

    report = "\n".join(lines) + "\n"
    out_path = ROOT / "coverage-by-file.txt"
    out_path.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
