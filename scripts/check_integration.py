#!/usr/bin/env python3
"""Validate template url_for endpoints and model/DB schema alignment."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RENDER_TEMPLATE_RE = re.compile(
    r"""(?:render_template(?:_string)?|\.render)\(\s*['"]([^'"]+)['"]"""
)
TEMPLATE_REF_RE = re.compile(
    r"""(?:extends|include)\s+['"]([^'"]+)['"]"""
)


def _collect_rendered_templates() -> set[str]:
    rendered: set[str] = set()
    skip_dirs = {"migrations", "venv", ".venv", "node_modules", "__pycache__", ".git"}
    for py in ROOT.rglob("*.py"):
        if skip_dirs.intersection(py.parts):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in RENDER_TEMPLATE_RE.finditer(text):
            rendered.add(m.group(1))
    return rendered


def _template_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    templates_dir = ROOT / "templates"
    for p in templates_dir.rglob("*.html"):
        rel = p.relative_to(templates_dir).as_posix()
        text = p.read_text(encoding="utf-8", errors="ignore")
        graph[rel] = {m.group(1) for m in TEMPLATE_REF_RE.finditer(text)}
    return graph


def _reachable_templates(rendered: set[str], graph: dict[str, set[str]]) -> set[str]:
    reachable = set(rendered)
    stack = list(rendered)
    while stack:
        current = stack.pop()
        for ref in graph.get(current, ()):
            if ref not in reachable:
                reachable.add(ref)
                stack.append(ref)
    return reachable


def _orphan_page_templates(rendered: set[str]) -> list[str]:
    """Page templates not reachable from any render_template() call."""
    graph = _template_graph()
    reachable = _reachable_templates(rendered, graph)
    orphans: list[str] = []
    templates_dir = ROOT / "templates"
    for p in templates_dir.rglob("*.html"):
        rel = p.relative_to(templates_dir).as_posix()
        if rel.startswith("_archive/"):
            continue
        if rel.startswith("includes/") or "/_" in rel or rel.startswith("_"):
            continue
        if rel not in reachable:
            orphans.append(rel)
    return sorted(orphans)


def main() -> int:
    from factory import create_app
    from extensions import db
    from sqlalchemy import inspect

    app = create_app()
    errors: list[str] = []
    warnings: list[str] = []

    with app.app_context():
        endpoints = set(app.view_functions.keys())
        pattern = re.compile(r"""url_for\(\s*['"]([^'"]+)['"]""")
        for p in (ROOT / "templates").rglob("*.html"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for m in pattern.finditer(text):
                ep = m.group(1)
                if ep.startswith("_"):
                    continue
                if ep not in endpoints:
                    rel = p.relative_to(ROOT)
                    errors.append(f"url_for missing endpoint '{ep}' in {rel}")

        insp = inspect(db.engine)
        db_tables = set(insp.get_table_names()) - {"alembic_version"}
        model_tables = set(db.metadata.tables.keys())
        if model_tables - db_tables:
            errors.append(f"tables missing in DB: {sorted(model_tables - db_tables)}")
        if db_tables - model_tables:
            errors.append(f"extra DB tables (no model): {sorted(db_tables - model_tables)}")

        for tname, table in db.metadata.tables.items():
            if tname not in insp.get_table_names():
                continue
            db_cols = {c["name"] for c in insp.get_columns(tname)}
            model_cols = {c.name for c in table.columns}
            miss = sorted(model_cols - db_cols)
            extra = sorted(db_cols - model_cols)
            if miss or extra:
                errors.append(f"{tname}: missing cols {miss}, extra cols {extra}")

        rendered = _collect_rendered_templates()
        orphans = _orphan_page_templates(rendered)
        if orphans:
            warnings.append(
                "orphan page templates (unreachable from routes): "
                + ", ".join(orphans))

    if warnings:
        print("INTEGRATION WARNINGS")
        for w in warnings:
            print("-", w)

    if errors:
        print("INTEGRATION CHECK FAILED")
        for e in errors:
            print("-", e)
        return 1

    print("INTEGRATION CHECK OK")
    print(f"  endpoints: {len(endpoints)}")
    print(f"  model tables: {len(model_tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
