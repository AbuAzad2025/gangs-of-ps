"""In-game currency helpers for the market (cash + bank, not real money)."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from extensions import db
from models.user import User
from models.market import UserInvestment
from services.resource_service import ResourceService
from services.economy_integrity import ABSOLUTE_MAX_MONEY_DELTA, parse_bank_amount


MIN_SPOT_TRADE = 10
MIN_FUTURES_MARGIN = 5
MAX_TRADE_QUANTITY = 1_000_000_000.0


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
    parsed = parse_bank_amount(amount, min_value=1)
    if parsed is None:
        return False, _msg('مبلغ غير صالح.'), {}
    amount_int = parsed

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


def parse_trade_usd(raw, *, min_value: float = MIN_SPOT_TRADE) -> float | None:
    """Sanitize USD trade size (spot buy, margin, intel)."""
    min_int = max(1, int(min_value))
    parsed = parse_bank_amount(raw, min_value=min_int)
    if parsed is not None:
        return float(parsed)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < min_value or value > ABSOLUTE_MAX_MONEY_DELTA:
        return None
    return value


def parse_trade_quantity(raw, *, min_value: float = 0.0) -> float | None:
    """Sanitize share/crypto quantity for sell/limit orders."""
    try:
        qty = float(raw)
    except (TypeError, ValueError):
        return None
    if qty <= min_value or qty > MAX_TRADE_QUANTITY:
        return None
    return qty


def parse_limit_price(raw) -> float | None:
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return None
    if price <= 0 or price > ABSOLUTE_MAX_MONEY_DELTA:
        return None
    return price


def _upsert_investment(
    user_id: int,
    asset_id: int,
    quantity: float,
    cost_usd: float,
    fallback_price: float,
) -> UserInvestment:
    investment = UserInvestment.query.filter_by(
        user_id=user_id, asset_id=asset_id).with_for_update().first()
    if investment:
        total_cost_old = investment.quantity * investment.average_buy_price
        total_qty = investment.quantity + quantity
        if total_qty > 0:
            investment.average_buy_price = (total_cost_old + cost_usd) / total_qty
        investment.quantity = total_qty
        return investment
    investment = UserInvestment(
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        average_buy_price=fallback_price,
    )
    db.session.add(investment)
    return investment


def execute_spot_buy(
    user_id: int,
    asset,
    amount_usd: float,
    action: str,
) -> Tuple[bool, Optional[str], Dict[str, int]]:
    """Atomic spot purchase: debit game balance + update portfolio in one savepoint."""
    amount = parse_trade_usd(amount_usd)
    if amount is None:
        return False, _msg('مبلغ غير صالح.'), {}
    if not asset or asset.current_price <= 0:
        return False, _msg('سعر غير صالح حالياً.'), {}
    quantity = amount / asset.current_price
    try:
        with db.session.begin_nested():
            ok, err, br = pay_from_game_balance(
                user_id, amount, action, auto_commit=False)
            if not ok:
                raise ValueError(err or _msg('رصيد اللعبة غير كافٍ.'))
            _upsert_investment(
                user_id, asset.id, quantity, amount, asset.current_price)
        db.session.commit()
        return True, None, br
    except ValueError as exc:
        db.session.rollback()
        return False, str(exc), {}
    except Exception:
        db.session.rollback()
        return False, _msg('فشل الشراء.'), {}


def execute_spot_sell_all(
    user_id: int,
    asset,
    action: str = 'sell_asset_spot',
) -> Tuple[bool, Optional[str], int]:
    """Atomic full-position sell: credit cash + remove investment in one savepoint."""
    if not asset or asset.current_price <= 0:
        return False, _msg('سعر غير صالح حالياً.'), 0
    try:
        with db.session.begin_nested():
            db.session.query(User).filter_by(id=user_id).with_for_update().first()
            investment = UserInvestment.query.filter_by(
                user_id=user_id, asset_id=asset.id).with_for_update().first()
            if not investment or investment.quantity <= 0:
                raise ValueError(_msg('لا تملك أسهم لبيعها!'))
            sell_value = investment.quantity * asset.current_price
            db.session.delete(investment)
            if not ResourceService.modify_resources(
                user_id,
                {'money': sell_value},
                action,
                auto_commit=False,
                expected_version=None,
            ):
                raise ValueError(_msg('خطأ في العملية!'))
        db.session.commit()
        return True, None, int(sell_value)
    except ValueError as exc:
        db.session.rollback()
        return False, str(exc), 0
    except Exception:
        db.session.rollback()
        return False, _msg('حدث خطأ أثناء البيع!'), 0


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
