#!/usr/bin/env python3
"""Run all QA checks locally before CI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS: list[tuple[str, list[str]]] = [
    ("Flake8 Lint", ["flake8", "."]),
    ("PyTest Unit Tests", ["python", "-m", "pytest", "tests/", "-x", "-v", "--tb=short"]),
    ("Integration Check", ["python", "scripts/check_integration.py"]),
]


def main() -> int:
    failures = 0
    for name, cmd in CHECKS:
        print(f"\n{'='*60}")
        print(f"  RUNNING: {name}")
        print(f"  CMD: {' '.join(cmd)}")
        print(f"{'='*60}")
        result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
        if result.returncode != 0:
            print(f"  FAILED: {name} (exit code {result.returncode})")
            failures += 1
        else:
            print(f"  PASSED: {name}")

    print(f"\n{'='*60}")
    if failures:
        print(f"  {failures} check(s) FAILED")
    else:
        print("  ALL CHECKS PASSED")
    print(f"{'='*60}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
