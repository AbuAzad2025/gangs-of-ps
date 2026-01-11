from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_

from extensions import db
from models.log import UserLog
from models.system import SystemConfig
from models.user import User


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


def _month_bounds(month_key: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    if not month_key:
        return None, None
    s = month_key.strip()
    if not s:
        return None, None
    try:
        year_s, month_s = s.split("-", 1)
        year = int(year_s)
        month = int(month_s)
        if month < 1 or month > 12:
            return None, None
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        return start, end
    except Exception:
        return None, None


def _get_report_start_at() -> Optional[datetime]:
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
class RevenueRow:
    user_id: int
    username: str
    payments: Dict[str, float]
    resources: Dict[str, int]
    ops: int
    last_at: Optional[datetime]


class RevenueService:
    RESOURCE_FIELDS = ("money", "bank_balance", "diamonds", "bullets")
    ACTION_REAL_MONEY = "ADMIN_REAL_MONEY_PURCHASE"

    @staticmethod
    def real_money_report(month: Optional[str] = None, search: Optional[str] = None, limit: int = 5000) -> Dict[str, Any]:
        start, end = _month_bounds(month)
        reset_at = _get_report_start_at()
        if reset_at and (start is None or reset_at > start):
            start = reset_at
        if reset_at and end and end <= reset_at:
            return {
                "rows": [],
                "totals": {"payments": {}, "resources": {}, "ops": 0, "users": 0},
                "filters": {"month": month or "", "search": search or ""},
                "months": [],
                "start_at": reset_at,
            }
        q = (
            db.session.query(UserLog, User.username)
            .join(User, UserLog.user_id == User.id)
            .filter(UserLog.action == RevenueService.ACTION_REAL_MONEY)
        )
        if start:
            q = q.filter(UserLog.timestamp >= start)
        if end:
            q = q.filter(UserLog.timestamp < end)
        if search:
            s = search.strip()
            if s:
                q = q.filter(User.username.ilike(f"%{s}%"))

        q = q.order_by(UserLog.timestamp.desc()).limit(int(max(1, min(limit, 20000))))

        by_user: Dict[int, RevenueRow] = {}
        totals_payments: Dict[str, float] = defaultdict(float)
        totals_resources: Dict[str, int] = defaultdict(int)

        for log, username in q.all():
            details = _parse_json_maybe(getattr(log, "details", None))
            if not isinstance(details, dict):
                continue

            cur = str(details.get("real_money_currency") or details.get("currency") or "USD").upper()
            try:
                paid = float(details.get("real_money_amount") or details.get("amount") or 0)
            except Exception:
                paid = 0.0

            res_delta: Dict[str, int] = {}
            for f in RevenueService.RESOURCE_FIELDS:
                v = details.get(f)
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)) and v != 0:
                    res_delta[f] = int(v)

            if paid <= 0 and not res_delta:
                continue

            row = by_user.get(log.user_id)
            if not row:
                row = RevenueRow(
                    user_id=int(log.user_id),
                    username=str(username),
                    payments=defaultdict(float),  # type: ignore[arg-type]
                    resources=defaultdict(int),  # type: ignore[arg-type]
                    ops=0,
                    last_at=None,
                )
                by_user[log.user_id] = row

            row.ops += 1
            if log.timestamp:
                if row.last_at is None or log.timestamp > row.last_at:
                    row.last_at = log.timestamp

            if paid > 0:
                row.payments[cur] += paid
                totals_payments[cur] += paid

            for k, v in res_delta.items():
                row.resources[k] += int(v)
                totals_resources[k] += int(v)

        rows = list(by_user.values())
        rows.sort(key=lambda r: sum(r.payments.values()), reverse=True)

        months = RevenueService._available_months(reset_at=reset_at)

        return {
            "rows": rows,
            "totals": {
                "payments": dict(totals_payments),
                "resources": dict(totals_resources),
                "ops": sum(r.ops for r in rows),
                "users": len(rows),
            },
            "filters": {"month": month or "", "search": search or ""},
            "months": months,
            "start_at": reset_at,
        }

    @staticmethod
    def _available_months(limit: int = 18, reset_at: Optional[datetime] = None) -> List[str]:
        q = UserLog.query.filter(UserLog.action == RevenueService.ACTION_REAL_MONEY)
        if reset_at:
            q = q.filter(UserLog.timestamp >= reset_at)
        q = q.order_by(UserLog.timestamp.desc()).limit(2500).all()
        seen = []
        seen_set = set()
        for log in q:
            ts = getattr(log, "timestamp", None)
            if not ts:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            key = f"{ts.year:04d}-{ts.month:02d}"
            if key in seen_set:
                continue
            seen_set.add(key)
            seen.append(key)
            if len(seen) >= limit:
                break
        return seen
