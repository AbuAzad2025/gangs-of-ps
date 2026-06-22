"""Empire command-center aggregates."""
from __future__ import annotations

from typing import Any, Dict, List

from services.economy_academy import compute_economy_health, get_peer_wealth_stats
from services.season_service import get_user_season_rank


def get_empire_dashboard(user, *, heat: int = 0, gang=None) -> Dict[str, Any]:
    cash = int(user.money or 0)
    bank = int(user.bank_balance or 0)
    diamonds = int(user.diamonds or 0)
    wealth = cash + bank
    health = compute_economy_health(user)
    peers = get_peer_wealth_stats(user)

    empire_score = min(
        100,
        max(
            5,
            int(health["score"] * 0.4)
            + min(30, int(user.level or 1) * 2)
            + min(20, wealth // 50000)
            + (10 if gang else 0)
            - min(15, int(heat)),
        ),
    )

    quick_actions: List[Dict[str, str]] = [
        {"url": "bank.index", "icon": "fa-university", "label": "البنك"},
        {"url": "market.index", "icon": "fa-chart-line", "label": "البورصة"},
        {"url": "main.crimes", "icon": "fa-mask", "label": "الجرائم"},
        {"url": "main.daily_tasks", "icon": "fa-tasks", "label": "المهام"},
        {"url": "economy.academy", "icon": "fa-graduation-cap", "label": "مدرسة الحارة"},
        {"url": "main.empire", "icon": "fa-crown", "label": "الإمبراطورية"},
    ]

    season_rank = get_user_season_rank(user.id)

    return {
        "wealth": wealth,
        "cash": cash,
        "bank": bank,
        "diamonds": diamonds,
        "heat": int(heat or 0),
        "gang": gang,
        "economy_health": health,
        "peers": peers,
        "empire_score": empire_score,
        "season_rank": season_rank,
        "quick_actions": quick_actions,
    }
