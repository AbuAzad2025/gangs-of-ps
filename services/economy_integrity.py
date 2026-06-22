"""Anti-cheat helpers: validate amounts and log suspicious economy actions."""
from __future__ import annotations

from flask import current_app

# Hard ceilings — override via SystemConfig where noted in callers
ABSOLUTE_MAX_MONEY_DELTA = 2_000_000_000
ABSOLUTE_MAX_DIAMOND_DELTA = 100_000
ABSOLUTE_MAX_STAKE = 500_000_000


def parse_positive_int(
    raw,
    *,
    default: int = 0,
    min_value: int = 0,
    max_value: int | None = None,
) -> int | None:
    """Return int in range, or None if invalid."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < min_value:
        return None
    cap = max_value if max_value is not None else ABSOLUTE_MAX_MONEY_DELTA
    if value > cap:
        return None
    return value


def log_suspicious(user_id: int, action: str, detail: str) -> None:
    try:
        current_app.logger.warning(
            'ECON_INTEGRITY user=%s action=%s detail=%s',
            user_id,
            action,
            detail,
        )
    except Exception:
        pass
