"""Global world events — SystemConfig toggles."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from models.system import SystemConfig


def _cfg(key: str, default: str = "") -> str:
    try:
        return str(SystemConfig.get_value(key, default) or default)
    except Exception:
        return default


def get_active_world_event() -> Optional[Dict[str, Any]]:
    active = _cfg("world_event_active", "false").lower() in ("1", "true", "yes")
    if not active:
        return None
    ends_raw = _cfg("world_event_ends_at", "")
    if ends_raw:
        try:
            ends = datetime.fromisoformat(ends_raw.replace("Z", "+00:00"))
            if ends.tzinfo is None:
                ends = ends.replace(tzinfo=timezone.utc)
            if ends <= datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    try:
        bonus_pct = float(_cfg("world_event_money_bonus_pct", "0") or 0)
    except Exception:
        bonus_pct = 0.0
    return {
        "title": _cfg("world_event_title", "حدث عالمي"),
        "description": _cfg("world_event_description", ""),
        "event_type": _cfg("world_event_type", "general"),
        "money_bonus_pct": bonus_pct,
        "icon": _cfg("world_event_icon", "fa-bolt"),
    }


def apply_world_event_money_bonus(base_amount: int) -> int:
    ev = get_active_world_event()
    if not ev or not base_amount:
        return int(base_amount)
    pct = float(ev.get("money_bonus_pct") or 0)
    if pct <= 0:
        return int(base_amount)
    return int(base_amount * (1 + pct / 100.0))
