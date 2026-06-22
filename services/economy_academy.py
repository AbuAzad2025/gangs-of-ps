"""
Economy Academy — تعليم اقتصادي تفاعلي داخل اللعبة.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from extensions import db
from models.facility import UserFacility
from models.user import User
from services.economy import calculate_bank_fee, get_bank_fee_config

ECONOMY_TASK_PREFIX = "مدرسة الحارة - يوم "
ONBOARDING_TASK_PREFIX = "أسبوع أول - يوم "
ACADEMY_LESSON_DAYS = 5


def _msg(text, **kwargs):
    try:
        from flask_babel import gettext as _
        if kwargs:
            return _(text, **kwargs)
        return _(text)
    except Exception:
        if kwargs:
            try:
                return text % kwargs
            except Exception:
                return text
        return text


@dataclass
class AcademyLesson:
    day: int
    title: str
    summary: str
    tip: str
    try_url: str
    try_label: str
    icon: str
    target_type: str


def get_academy_lessons() -> List[AcademyLesson]:
    from flask import url_for

    return [
        AcademyLesson(
            day=1,
            title=_msg("البنك والأمان"),
            summary=_msg("الكاش في جيبك عُرضة للسرقة. البنك يحمي أموالك لكنه يفرض رسوماً على الأرصدة الكبيرة."),
            tip=_msg("قاعدة ذهبية: احتفظ بكاش للمصاريف اليومية، والباقي أودعه."),
            try_url=url_for("bank.index"),
            try_label=_msg("اذهب للبنك"),
            icon="fa-university",
            target_type="bank_deposit",
        ),
        AcademyLesson(
            day=2,
            title=_msg("السوق والعرض"),
            summary=_msg("السوق السوداء تربحك من فرق الشراء والبيع. اشترِ رخيصاً وبِع بربح."),
            tip=_msg("قارن الأسعار قبل الشراء — المزادات أحياناً أرخص."),
            try_url=url_for("black_market.index"),
            try_label=_msg("افتح السوق السوداء"),
            icon="fa-store-slash",
            target_type="buy",
        ),
        AcademyLesson(
            day=3,
            title=_msg("البورصة والمخاطرة"),
            summary=_msg(
                "تداول بكاشك من الجرائم والبنك (مال اللعبة فقط). "
                "اشترِ بمبلغ صغير من أصل واحد على الأقل وراقب الربح/الخسارة."
            ),
            tip=_msg(
                "الحد الأدنى 10$ من مال اللعبة. إذا الكاش قليل، يُخصم من البنك تلقائياً. "
                "لا تضع أكثر من 15%% من رصيدك في صفقة واحدة."
            ),
            try_url=url_for("market.index"),
            try_label=_msg("افتح البورصة وتداول"),
            icon="fa-chart-line",
            target_type="market_trade",
        ),
        AcademyLesson(
            day=4,
            title=_msg("الإنتاج والمصانع"),
            summary=_msg("المصانع تحوّل المواد لمنتجات تُباع بربح. الإنتاج أبطأ من السرقة لكنه مستدام."),
            tip=_msg("وظّف عمالاً ولا تنسَ تكلفة المواد الخام."),
            try_url=url_for("factory.index"),
            try_label=_msg("زر المصنع"),
            icon="fa-industry",
            target_type="factory_visit",
        ),
        AcademyLesson(
            day=5,
            title=_msg("الصيانة والتكاليف"),
            summary=_msg("كل يوم تدفع رسوم بنكية وصيانة ممتلكات. تتبّع سجل مواردك لتعرف أين يذهب المال."),
            tip=_msg("راجع السجل أسبوعياً — المصاريف الخفية تقتل الإمبراطورية."),
            try_url=url_for("resources.my_ledger"),
            try_label=_msg("سجل الموارد"),
            icon="fa-file-invoice-dollar",
            target_type="ledger_visit",
        ),
    ]


def get_lesson_for_day(day: int) -> Optional[AcademyLesson]:
    if day < 1 or day > ACADEMY_LESSON_DAYS:
        return None
    for lesson in get_academy_lessons():
        if lesson.day == day:
            return lesson
    return None


def estimate_user_maintenance(user_id: int) -> int:
    from models.system import SystemConfig

    try:
        maint_multiplier = float(
            SystemConfig.get_value("maintenance_multiplier", 1.0)
        )
    except Exception:
        maint_multiplier = 1.0

    base_costs = {
        "house": 500,
        "warehouse": 1000,
        "lab": 2000,
        "bunker": 5000,
    }
    total = 0
    facilities = UserFacility.query.filter_by(user_id=user_id).filter(
        UserFacility.level > 0
    ).all()
    for fac in facilities:
        base = base_costs.get(fac.facility_key, 500)
        total += int(base * (fac.level or 0) * maint_multiplier)
    return total


def preview_bank_fee(balance: int) -> Dict[str, Any]:
    config = get_bank_fee_config()
    fee, reason = calculate_bank_fee(max(0, int(balance or 0)), config)
    return {
        "balance": int(balance or 0),
        "fee": int(fee),
        "reason": reason,
        "tier1_threshold": config["tier1_threshold"],
        "tier2_threshold": config["tier2_threshold"],
    }


def get_peer_wealth_stats(user: User) -> Dict[str, Any]:
    level = int(user.level or 1)
    row = (
        db.session.query(
            func.avg(User.money + User.bank_balance).label("avg_wealth"),
            func.count(User.id).label("peer_count"),
        )
        .filter(User.level == level, User.id != user.id)
        .first()
    )
    avg_wealth = int(row.avg_wealth or 0) if row else 0
    peer_count = int(row.peer_count or 0) if row else 0
    user_wealth = int((user.money or 0) + (user.bank_balance or 0))
    diff = user_wealth - avg_wealth
    return {
        "level": level,
        "user_wealth": user_wealth,
        "avg_wealth": avg_wealth,
        "peer_count": peer_count,
        "diff": diff,
        "ahead": diff > 0,
    }


def compute_economy_health(user: User) -> Dict[str, Any]:
    cash = int(user.money or 0)
    bank = int(user.bank_balance or 0)
    total = cash + bank
    if total <= 0:
        cash_pct = 100
        bank_pct = 0
    else:
        cash_pct = int(round(cash * 100 / total))
        bank_pct = 100 - cash_pct

    bank_fee_info = preview_bank_fee(bank)
    maintenance = estimate_user_maintenance(user.id)
    daily_sink = int(bank_fee_info["fee"]) + maintenance

    score = 55
    if 25 <= bank_pct <= 75:
        score += 20
    elif bank_pct > 0:
        score += 8
    if cash_pct > 85:
        score -= 18
    if cash_pct < 5 and total > 1000:
        score -= 10
    if bank_fee_info["fee"] > 0:
        score -= min(15, int(bank_fee_info["fee"] / max(1, total) * 100))
    if maintenance > 0 and maintenance > cash * 0.5:
        score -= 10
    score = max(5, min(100, score))

    if score >= 75:
        label = _msg("ممتاز")
        status = "success"
    elif score >= 50:
        label = _msg("متوازن")
        status = "warning"
    else:
        label = _msg("يحتاج تحسين")
        status = "danger"

    tips: List[str] = []
    if cash_pct > 80 and total > 500:
        tips.append(_msg("أغلب ثروتك كاش — عُرضة للسرقة في القتال. فكّر بالإيداع."))
    if bank_fee_info["fee"] > 500:
        tips.append(
            _msg("رسوم البنك اليومية ~%(fee)s$ — قلّل الرصيد أو استثمره.", fee=f"{bank_fee_info['fee']:,}")
        )
    if maintenance > 0:
        tips.append(_msg("صيانة الممتلكات ~%(amt)s$/يوم — راقبها في السجل.", amt=f"{maintenance:,}"))
    if bank_pct == 0 and total > 2000:
        tips.append(_msg("لا تملك رصيداً في البنك — الإيداع يحمي جزءاً من ثروتك."))

    return {
        "score": score,
        "label": label,
        "status": status,
        "cash": cash,
        "bank": bank,
        "total": total,
        "cash_pct": cash_pct,
        "bank_pct": bank_pct,
        "daily_sink": daily_sink,
        "bank_fee": bank_fee_info["fee"],
        "maintenance": maintenance,
        "tips": tips,
    }


def get_lesson_progress(user, today=None) -> List[Dict[str, Any]]:
    from datetime import datetime, timezone

    from models.gameplay import DailyTask, UserDailyTask
    from routes.utils import get_onboarding_day

    if today is None:
        today = datetime.now(timezone.utc).date()

    onboarding_day = get_onboarding_day(user, today=today)
    lessons = get_academy_lessons()
    progress_rows = (
        UserDailyTask.query.join(DailyTask)
        .filter(
            UserDailyTask.user_id == user.id,
            DailyTask.description.like(f"{ECONOMY_TASK_PREFIX}%"),
        )
        .all()
    )
    completed_days = set()
    for row in progress_rows:
        desc = row.task.description or ""
        if row.is_completed and desc.startswith(ECONOMY_TASK_PREFIX):
            try:
                day_part = desc.split(" - يوم ", 1)[1].split(":", 1)[0]
                completed_days.add(int(day_part.strip()))
            except Exception:
                pass

    result = []
    for lesson in lessons:
        locked = False
        if onboarding_day is not None:
            locked = lesson.day > onboarding_day
        elif lesson.day > 1:
            locked = lesson.day not in completed_days and lesson.day > 1

        result.append(
            {
                "day": lesson.day,
                "title": lesson.title,
                "summary": lesson.summary,
                "tip": lesson.tip,
                "try_url": lesson.try_url,
                "try_label": lesson.try_label,
                "icon": lesson.icon,
                "locked": locked,
                "completed": lesson.day in completed_days,
                "current": onboarding_day == lesson.day if onboarding_day else False,
            }
        )
    return result
