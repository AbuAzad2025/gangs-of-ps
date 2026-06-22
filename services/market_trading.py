"""In-game currency helpers for the market (cash + bank, not real money)."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from extensions import db
from models.user import User
from services.resource_service import ResourceService


MIN_SPOT_TRADE = 10
MIN_FUTURES_MARGIN = 5


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


def get_trading_power(user) -> Dict[str, int]:
    cash = int(getattr(user, 'money', 0) or 0)
    bank = int(getattr(user, 'bank_balance', 0) or 0)
    return {
        'cash': cash,
        'bank': bank,
        'total': cash + bank,
    }


def pay_from_game_balance(
    user_id: int,
    amount: float,
    action: str,
    *,
    allow_bank: bool = True,
    auto_commit: bool = True,
) -> Tuple[bool, Optional[str], Dict[str, int]]:
    """Pay using in-game cash first, then bank if needed."""
    try:
        amount_int = int(round(float(amount)))
    except (TypeError, ValueError):
        return False, _msg('مبلغ غير صالح.'), {}

    if amount_int <= 0:
        return False, _msg('مبلغ غير صالح.'), {}

    user = db.session.get(User, user_id)
    if not user:
        return False, _msg('المستخدم غير موجود.'), {}

    power = get_trading_power(user)
    spendable = power['total'] if allow_bank else power['cash']
    if spendable < amount_int:
        return False, _msg(
            'رصيد اللعبة غير كافٍ. الكاش: %(cash)s$ — البنك: %(bank)s$.',
            cash=f"{power['cash']:,}",
            bank=f"{power['bank']:,}",
        ), {}

    from_cash = min(power['cash'], amount_int)
    from_bank = amount_int - from_cash
    if from_bank > 0 and not allow_bank:
        return False, _msg('الكاش غير كافٍ. اسحب من البنك أو قلّل المبلغ.'), {}

    changes = {}
    if from_cash:
        changes['money'] = -from_cash
    if from_bank:
        changes['bank_balance'] = -from_bank

    ok = ResourceService.modify_resources(
        user_id,
        changes,
        action,
        auto_commit=auto_commit,
        expected_version=None,
        check_balance=True,
    )
    if not ok:
        return False, _msg('فشل خصم رصيد اللعبة.'), {}

    return True, None, {'from_cash': from_cash, 'from_bank': from_bank}


def trade_success_flash(breakdown: Dict[str, int]) -> Optional[str]:
    from_bank = int(breakdown.get('from_bank') or 0)
    from_cash = int(breakdown.get('from_cash') or 0)
    if from_bank > 0 and from_cash > 0:
        return _msg(
            'تم الدفع من كاش اللعبة (%(cash)s$) والبنك (%(bank)s$).',
            cash=f"{from_cash:,}",
            bank=f"{from_bank:,}",
        )
    if from_bank > 0:
        return _msg('تم الدفع من رصيد البنك (%(bank)s$).', bank=f"{from_bank:,}")
    return None
