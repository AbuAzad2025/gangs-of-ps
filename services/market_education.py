"""
تعليم السوق — ربط ميكانيكا اللعبة بمفاهيم اقتصاد حقيقية.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.market import MarketAsset, UserInvestment


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


def get_market_concepts() -> List[Dict[str, str]]:
    """مفاهيم حقيقية يتعلمها اللاعب من التداول."""
    return [
        {
            "icon": "fa-balance-scale",
            "title": _msg("العرض والطلب (مبسّط)"),
            "body": _msg(
                "في العالم الحقيقي يرتفع السعر عندما المشترون أقوى من البائعين. "
                "هنا الأسعار تتحرك عشوائياً لمحاكاة التقلب — تعلّم قراءة الحركة دون الاعتماد على توقع مضمون."
            ),
        },
        {
            "icon": "fa-chart-pie",
            "title": _msg("التنويع (Diversification)"),
            "body": _msg(
                "لا تضع كل المال في أصل واحد. وزّع بين أسهم مستقرة وعملات متقلبة "
                "ليقل خسارتك إذا هبط أصل واحد."
            ),
        },
        {
            "icon": "fa-calculator",
            "title": _msg("متوسط التكلفة وربح/خسارة غير محققة"),
            "body": _msg(
                "سعر الشراء المتوسط يحدد هل أنت رابح أم خاسر قبل البيع. "
                "في الحياة الحقيقية: لا تحسب الربح إلا بعد البيع الفعلي (realized P/L)."
            ),
        },
        {
            "icon": "fa-bolt",
            "title": _msg("التقلب والمخاطرة"),
            "body": _msg(
                "العملات الرقمية أسرع حركة من الأسهم — ربح أعلى وخسارة أسرع. "
                "قاعدة عملية: كلما زاد التقلب، قلّل حجم الصفقة."
            ),
        },
        {
            "icon": "fa-hand-holding-usd",
            "title": _msg("حجم الصفقة وإدارة رأس المال"),
            "body": _msg(
                "لا تستثمر أكثر من 10–20%% من كاشك في صفقة واحدة حتى تتعلم. "
                "احتفظ باحتياطي للمصاريف اليومية والبنك."
            ),
        },
        {
            "icon": "fa-layer-group",
            "title": _msg("أوامر السوق مقابل المحددة"),
            "body": _msg(
                "أمر السوق ينفّذ فوراً بسعر اليوم. أمر محدد ينتظر سعرك — "
                "مثل انتظار خصم على منتج قبل الشراء."
            ),
        },
        {
            "icon": "fa-exclamation-triangle",
            "title": _msg("الرافعة المالية (Futures)"),
            "body": _msg(
                "الرافعة تضخّم الربح والخسارة. في الواقع واللعبة: خطأ صغير قد يصفّر الهامش. "
                "تعلّمها بعد إتقان الشراء والبيع العادي."
            ),
        },
    ]


def analyze_portfolio(
    investments: List[UserInvestment],
    assets_by_id: Optional[Dict[int, MarketAsset]] = None,
    cash: int = 0,
    bank: int = 0,
) -> Dict[str, Any]:
    """نصائح تعليمية مبنية على محفظة اللاعب الفعلية."""
    tips: List[str] = []
    if not investments:
        tips.append(_msg("ابدأ بصفقة صغيرة (من 10$) من كاش أو بنك اللعبة."))
        tips.append(_msg("اقرأ أكاديمية السوق ثم جرّب أصلين مختلفين: سهم مستقر + عملة رقمية."))
        return {
            "diversification_score": 0,
            "diversification_label": _msg("لم تبدأ بعد"),
            "asset_count": 0,
            "largest_weight_pct": 0,
            "tips": tips,
        }

    total_value = 0.0
    rows = []
    for inv in investments:
        if not inv.quantity or inv.quantity <= 0:
            continue
        val = float(inv.current_value())
        total_value += val
        asset = assets_by_id.get(inv.asset_id) if assets_by_id else inv.asset
        atype = getattr(asset, "asset_type", "stock") if asset else "stock"
        rows.append({"value": val, "type": atype, "symbol": getattr(asset, "symbol", "?")})

    if total_value <= 0:
        return {
            "diversification_score": 0,
            "diversification_label": _msg("لا قيمة"),
            "asset_count": 0,
            "largest_weight_pct": 0,
            "tips": [_msg("محفظتك فارغة — جرّب شراء كمية صغيرة من أصل واحد.")],
        }

    rows.sort(key=lambda r: r["value"], reverse=True)
    largest_pct = int(round(rows[0]["value"] * 100 / total_value))
    types = {r["type"] for r in rows}
    asset_count = len(rows)

    score = 30
    if asset_count >= 2:
        score += 20
    if asset_count >= 3:
        score += 15
    if len(types) >= 2:
        score += 20
    if largest_pct <= 60:
        score += 10
    if largest_pct <= 40:
        score += 5
    score = max(0, min(100, score))

    if score >= 75:
        label = _msg("محفظة متنوعة جيداً")
    elif score >= 45:
        label = _msg("متوسطة — أضف أصنافاً")
    else:
        label = _msg("مركّزة — خطر أعلى")

    if largest_pct > 70:
        tips.append(
            _msg(
                "أكثر من %(pct)s%% في أصل واحد (%(sym)s) — في السوق الحقيقي هذا خطر تركيز.",
                pct=largest_pct,
                sym=rows[0]["symbol"],
            )
        )
    if "crypto" not in types and asset_count > 0:
        tips.append(_msg("لم تجرّب العملات الرقمية بعد — تعلّم الفرق بين تقلبها وأسهم الشركات."))
    if "stock" not in types and asset_count > 0:
        tips.append(_msg("الأسهم عادة أقل تقلباً — أضف سهماً لتوسيع المحفظة."))
    if cash > 0 and total_value > cash * 3:
        tips.append(_msg("معظم ثروتك في أصول — احتفظ بكاش احتياطي للفرص والطوارئ."))
    if not tips:
        tips.append(_msg("وازن بين المراجعة الدورية وعدم البيع بذعر عند أول هبوط."))

    return {
        "diversification_score": score,
        "diversification_label": label,
        "asset_count": asset_count,
        "largest_weight_pct": largest_pct,
        "tips": tips,
    }
