"""Collect real browser JavaScript coverage from the app's frontend assets."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def collect_browser_coverage(output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["node", str(ROOT / "tests" / "support" / "browser_coverage.mjs"), "--output", str(output_path)]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Browser coverage script failed"
        raise RuntimeError(message)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "coverage" / "browser-coverage.json")
    args = parser.parse_args()

    result = collect_browser_coverage(args.output)
    print(json.dumps({
        "source": result["source"],
        "percent": result["percent"],
        "executed_bytes": result["executed_bytes"],
        "total_bytes": result["total_bytes"],
        "scripts": result["scripts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
