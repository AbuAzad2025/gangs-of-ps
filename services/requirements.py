from flask_babel import _


def effective_level(user):
    try:
        return int(user.level + (user.rank_points_value // 50))
    except Exception:
        from extensions import db
        try:
            db.session.rollback()
        except BaseException:
            pass
        return int(user.level)


def tier_for_level(level):
    if level < 5:
        return "t1"
    if level < 15:
        return "t2"
    if level < 30:
        return "t3"
    if level < 60:
        return "t4"
    return "t5"


def tier_for_user(user):
    return tier_for_level(effective_level(user))


def tier_rank(tier):
    return {"t1": 1, "t2": 2, "t3": 3, "t4": 4, "t5": 5}.get(tier, 1)


def _as_int(x):
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


def check_requirements(user, req):
    req = dict(req or {})
    reasons = []
    missing = []
    tier = tier_for_user(user)

    min_tier = req.get("min_tier")
    if min_tier and tier_rank(tier) < tier_rank(min_tier):
        reasons.append(_('تحتاج رتبة أعلى (%(tier)s).', tier=min_tier))
        missing.append("tier")

    min_level = _as_int(req.get("min_level"))
    if min_level is not None and effective_level(user) < min_level:
        reasons.append(_('تحتاج مستوى %(n)s.', n=min_level))
        missing.append("level")

    min_exp = _as_int(req.get("min_exp"))
    if min_exp is not None and int(user.exp) < min_exp:
        reasons.append(_('تحتاج خبرة %(n)s.', n=min_exp))
        missing.append("exp")

    min_intel = _as_int(req.get("min_intelligence"))
    if min_intel is not None and int(
        getattr(
            user,
            "intelligence",
            0)) < min_intel:
        reasons.append(_('تحتاج ذكاء %(n)s.', n=min_intel))
        missing.append("intelligence")

    min_str = _as_int(req.get("min_strength"))
    if min_str is not None and int(getattr(user, "strength", 0)) < min_str:
        reasons.append(_('تحتاج قوة %(n)s.', n=min_str))
        missing.append("strength")

    min_agl = _as_int(req.get("min_agility"))
    if min_agl is not None and int(getattr(user, "agility", 0)) < min_agl:
        reasons.append(_('تحتاج رشاقة %(n)s.', n=min_agl))
        missing.append("agility")

    hint_key = None
    hint_text = None
    if missing:
        k = missing[0]
        if k in {"intelligence", "strength", "agility"}:
            hint_key = "gym"
            if k == "intelligence":
                hint_text = _('نصيحة: روح الجيم ودرّب الذكاء.')
            elif k == "strength":
                hint_text = _('نصيحة: روح الجيم ودرّب القوة.')
            else:
                hint_text = _('نصيحة: روح الجيم ودرّب الرشاقة.')
        elif k in {"tier", "level", "exp"}:
            hint_key = "daily_tasks"
            hint_text = _('نصيحة: نفّذ المهام اليومية لتتطور أسرع.')

    return {
        "ok": len(reasons) == 0,
        "tier": tier,
        "missing": missing,
        "reasons": reasons,
        "reason": reasons[0] if reasons else None,
        "hint_key": hint_key,
        "hint_text": hint_text,
    }
