from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import or_

from extensions import db
from models import UserLog, MoneySinkLog
from models.system import SystemConfig


def _aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_json_maybe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return None
    return None


def _extract_resource_deltas_from_log(log: UserLog, resources: Iterable[str]) -> Dict[str, int]:
    deltas: Dict[str, int] = {}
    details = _parse_json_maybe(getattr(log, "details", None))
    if isinstance(details, dict):
        for r in resources:
            v = details.get(r)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)) and v != 0:
                deltas[r] = int(v)
        if deltas:
            return deltas

    before_state = _parse_json_maybe(getattr(log, "before_state", None))
    after_state = _parse_json_maybe(getattr(log, "after_state", None))
    if isinstance(before_state, dict) and isinstance(after_state, dict):
        for r in resources:
            b = before_state.get(r)
            a = after_state.get(r)
            if isinstance(b, bool) or isinstance(a, bool):
                continue
            if isinstance(b, (int, float)) and isinstance(a, (int, float)):
                diff = int(a) - int(b)
                if diff != 0:
                    deltas[r] = diff
    return deltas


def _scenario_from_action(action: str) -> str:
    a = (action or "").upper()
    if not a:
        return "غير مصنّف"

    if a.startswith("ADMIN_") or a in {"DEVELOPER_POWER"}:
        return "تدخل إداري/مطور"
    if a.startswith("BANK_"):
        return "البنك والتحويلات"
    if a.startswith("CASINO_") or a in {"HIRE_HOSTESS"}:
        return "الكازينو"
    if a.startswith("GAME_"):
        return "الترفيه والرهانات"
    if a.startswith("AI_RACE_") or a.startswith("RACE_") or a in {"CREATE_RACE", "JOIN_RACE", "CANCEL_RACE_REFUND", "RACE_WIN"}:
        return "السباقات"
    if a.startswith("SPOT_") or a.startswith("FUTURES_") or a in {"BUY_INTEL_MARKET", "BUY_ASSET_SPOT", "SELL_ASSET_SPOT"}:
        return "السوق والتداول"
    if a.startswith("AUCTION_") or a in {"BUY_SMUGGLING", "SELL_SMUGGLING", "BUY_BLACK_MARKET_ITEM", "SELL_LOOT", "REPAIR_LOOT", "REPAIR_ALL_LOOT", "BUY_SERVICE_SAFEHOUSE", "BUY_SERVICE_DISGUISE", "BUY_SERVICE_COOL_OFF", "SPY"}:
        return "السوق السوداء"
    if a.startswith("HOSPITAL_"):
        return "المستشفى"
    if a.startswith("JAIL_"):
        return "السجن"
    if a.startswith("TRAVEL_") or a in {"SMUGGLING_BUST_FINE"}:
        return "التنقل والحواجز"
    if a.startswith("GANG_"):
        return "العصابة والخزنة"
    if a in {"BUY_PROPERTY", "PROPERTY_INCOME_COLLECTION"} or a.startswith("MAINTENANCE_"):
        return "العقارات والاقتصاد"
    if a.startswith("COMBAT_") or a in {"PLACE_BOUNTY", "BUY_OFF_BOUNTY"}:
        return "القتال والمكافآت"
    if a.startswith("FACTORY_"):
        return "المصنع"
    if a.startswith("FARM_"):
        return "المزرعة"
    if a.startswith("ROOM_"):
        return "الترفيه والرهانات"
    if a in {"INVESTIGATE_COST", "ORGANIZED_CRIME_LEAVE_PENALTY", "ORGANIZED_CRIME_REWARD", "CRIME_SUCCESS"} or a.startswith("DAILY_TASK_"):
        return "الجريمة والمهام"

    return "غير مصنّف"


def _sum_real_money_revenue(user_id: int, start: Optional[datetime] = None) -> Dict[str, float]:
    q = UserLog.query.filter(UserLog.user_id == user_id, UserLog.action == "REAL_MONEY_REVENUE")
    if start:
        q = q.filter(UserLog.timestamp >= start)
    totals: Dict[str, float] = defaultdict(float)
    for log in q.order_by(UserLog.timestamp.desc()).yield_per(300):
        details = _parse_json_maybe(getattr(log, "details", None))
        if not isinstance(details, dict):
            continue
        cur = str(details.get("currency") or "USD").upper()
        try:
            amt = float(details.get("amount") or 0)
        except Exception:
            amt = 0.0
        if amt > 0:
            totals[cur] += amt
    return dict(totals)


def _real_money_reset_at() -> Optional[datetime]:
    raw = None
    try:
        raw = SystemConfig.get_value("real_money_report_start_at", "")
    except Exception:
        raw = ""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
    except Exception:
        return None
    return dt.replace(tzinfo=None)


@dataclass
class BudgetRow:
    scenario: str
    count: int
    money_in: int
    money_out: int
    bank_in: int
    bank_out: int
    diamonds_in: int
    diamonds_out: int

    @property
    def money_net(self) -> int:
        return self.money_in - self.money_out

    @property
    def bank_net(self) -> int:
        return self.bank_in - self.bank_out

    @property
    def diamonds_net(self) -> int:
        return self.diamonds_in - self.diamonds_out

    @property
    def currency_in(self) -> int:
        return self.money_in + self.bank_in

    @property
    def currency_out(self) -> int:
        return self.money_out + self.bank_out

    @property
    def currency_net(self) -> int:
        return self.currency_in - self.currency_out


class BudgetService:
    RESOURCES = ("money", "bank_balance", "diamonds")

    @staticmethod
    def scenario_for_action(action: str) -> str:
        return _scenario_from_action(action or "")

    @staticmethod
    def extract_deltas(log: UserLog) -> Dict[str, int]:
        return _extract_resource_deltas_from_log(log, BudgetService.RESOURCES)

    @staticmethod
    def compute_user_budget(user_id: int, range_key: str = "30d") -> Dict[str, Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        range_key = (range_key or "30d").strip().lower()

        start: Optional[datetime] = None
        if range_key in {"7d", "7"}:
            start = now - timedelta(days=7)
            range_key = "7d"
        elif range_key in {"30d", "30"}:
            start = now - timedelta(days=30)
            range_key = "30d"
        elif range_key in {"90d", "90"}:
            start = now - timedelta(days=90)
            range_key = "90d"
        else:
            range_key = "all"

        q = UserLog.query.filter(UserLog.user_id == user_id)
        if start:
            q = q.filter(UserLog.timestamp >= start)

        q = q.filter(
            or_(
                UserLog.details.ilike("%money%"),
                UserLog.details.ilike("%bank_balance%"),
                UserLog.details.ilike("%diamonds%"),
                UserLog.action.in_(["ROOM_CREATE", "ROOM_JOIN", "ROOM_LEAVE", "ROOM_FINISH"]),
                UserLog.action.ilike("ADMIN_%"),
                UserLog.action.in_(["DEVELOPER_POWER"]),
                UserLog.action.ilike("BANK_%"),
            )
        ).order_by(UserLog.timestamp.desc())

        rows: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "money_in": 0, "money_out": 0, "bank_in": 0, "bank_out": 0, "diamonds_in": 0, "diamonds_out": 0})
        actions_seen: Dict[str, int] = defaultdict(int)

        for log in q.yield_per(500):
            action = (log.action or "").upper()
            deltas = BudgetService.extract_deltas(log)
            if not deltas:
                continue

            scenario = _scenario_from_action(action)
            bucket = rows[scenario]
            bucket["count"] += 1
            actions_seen[action] += 1

            money_delta = int(deltas.get("money", 0))
            bank_delta = int(deltas.get("bank_balance", 0))
            diamonds_delta = int(deltas.get("diamonds", 0))

            if money_delta > 0:
                bucket["money_in"] += money_delta
            elif money_delta < 0:
                bucket["money_out"] += abs(money_delta)

            if bank_delta > 0:
                bucket["bank_in"] += bank_delta
            elif bank_delta < 0:
                bucket["bank_out"] += abs(bank_delta)

            if diamonds_delta > 0:
                bucket["diamonds_in"] += diamonds_delta
            elif diamonds_delta < 0:
                bucket["diamonds_out"] += abs(diamonds_delta)

        sink_q = MoneySinkLog.query.filter(MoneySinkLog.user_id == user_id)
        sink_time_col = getattr(MoneySinkLog, "created_at", None) or getattr(MoneySinkLog, "timestamp", None)
        if start and sink_time_col is not None:
            sink_q = sink_q.filter(sink_time_col >= start)
        sink_rows = sink_q.with_entities(MoneySinkLog.sink_type, db.func.sum(MoneySinkLog.amount)).group_by(MoneySinkLog.sink_type).all()
        implicit_expenses = [{"type": t, "amount": int(a or 0)} for (t, a) in sink_rows if a]
        implicit_expenses.sort(key=lambda x: x["amount"], reverse=True)

        budget_rows: List[BudgetRow] = []
        totals = {"count": 0, "money_in": 0, "money_out": 0, "bank_in": 0, "bank_out": 0, "diamonds_in": 0, "diamonds_out": 0}
        for scenario, d in rows.items():
            r = BudgetRow(
                scenario=scenario,
                count=int(d["count"]),
                money_in=int(d["money_in"]),
                money_out=int(d["money_out"]),
                bank_in=int(d["bank_in"]),
                bank_out=int(d["bank_out"]),
                diamonds_in=int(d["diamonds_in"]),
                diamonds_out=int(d["diamonds_out"]),
            )
            budget_rows.append(r)
            totals["count"] += r.count
            totals["money_in"] += r.money_in
            totals["money_out"] += r.money_out
            totals["bank_in"] += r.bank_in
            totals["bank_out"] += r.bank_out
            totals["diamonds_in"] += r.diamonds_in
            totals["diamonds_out"] += r.diamonds_out

        budget_rows.sort(key=lambda r: (r.currency_out + r.money_out + r.bank_out + r.diamonds_out), reverse=True)

        top_actions = sorted(actions_seen.items(), key=lambda kv: kv[1], reverse=True)[:20]

        reset_at = _real_money_reset_at()
        real_start = start if range_key != "all" else None
        if reset_at and (real_start is None or reset_at > real_start):
            real_start = reset_at
        real_money_range = _sum_real_money_revenue(user_id, start=real_start)
        real_money_all_time = _sum_real_money_revenue(user_id, start=reset_at)

        return {
            "range": range_key,
            "start": start,
            "end": now,
            "totals": {
                **totals,
                "money_net": totals["money_in"] - totals["money_out"],
                "bank_net": totals["bank_in"] - totals["bank_out"],
                "diamonds_net": totals["diamonds_in"] - totals["diamonds_out"],
                "currency_in": totals["money_in"] + totals["bank_in"],
                "currency_out": totals["money_out"] + totals["bank_out"],
                "currency_net": (totals["money_in"] + totals["bank_in"]) - (totals["money_out"] + totals["bank_out"]),
            },
            "rows": [r.__dict__ | {"money_net": r.money_net, "bank_net": r.bank_net, "diamonds_net": r.diamonds_net, "currency_in": r.currency_in, "currency_out": r.currency_out, "currency_net": r.currency_net} for r in budget_rows],
            "implicit_expenses": implicit_expenses[:20],
            "top_actions": [{"action": a, "count": c, "scenario": _scenario_from_action(a)} for (a, c) in top_actions],
            "real_money": {
                "range": real_money_range,
                "all_time": real_money_all_time,
                "reset_at": reset_at,
            },
        }
