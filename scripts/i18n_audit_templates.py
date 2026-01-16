from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
JINJA_RE = re.compile(r"(\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\})", re.DOTALL)
TAG_TEXT_RE = re.compile(r">([^<]+)<")


@dataclass
class Finding:
    file: Path
    line: int
    text: str


def _iter_template_files() -> Iterable[Path]:
    for p in TEMPLATES_DIR.rglob("*.html"):
        yield p


def _line_number_for_offset(s: str, offset: int) -> int:
    return s.count("\n", 0, offset) + 1


def audit_file(path: Path) -> List[Finding]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    stripped = JINJA_RE.sub("", src)
    out: List[Finding] = []
    for m in TAG_TEXT_RE.finditer(stripped):
        raw = m.group(1)
        text = raw.strip()
        if not text:
            continue
        if not ARABIC_RE.search(text):
            continue
        if len(text) <= 1:
            continue
        if any(ch in text for ch in ["&nbsp;", "&#", "&amp;"]):
            continue
        line = _line_number_for_offset(stripped, m.start(1))
        out.append(Finding(file=path, line=line, text=text))
    return out


def main() -> None:
    findings: List[Finding] = []
    for f in _iter_template_files():
        findings.extend(audit_file(f))

    findings.sort(key=lambda x: (str(x.file), x.line))

    print(f"templates scanned: {len(list(_iter_template_files()))}")
    print(f"findings: {len(findings)}")
    for it in findings[:400]:
        rel = it.file.relative_to(ROOT)
        t = it.text.replace("\n", " ").strip()
        if len(t) > 140:
            t = t[:140] + "…"
        print(f"{rel}:{it.line}: {t}")

    if len(findings) > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
