"""Anti-cheat helpers: validate amounts and log suspicious economy actions."""
from __future__ import annotations

from flask import current_app

# Hard ceilings — override via SystemConfig where noted in callers
ABSOLUTE_MAX_MONEY_DELTA = 2_000_000_000
ABSOLUTE_MAX_DIAMOND_DELTA = 100_000
ABSOLUTE_MAX_STAKE = 500_000_000

MANUAL_DIAMOND_CATALOG = {10: 300, 20: 650, 50: 1700}
CUSTOM_MIN_USD = 10
CUSTOM_MAX_USD = 1000
CUSTOM_DIAMONDS_PER_USD = 30  # 30 diamonds per 1 USD for custom amounts


class SecurityBoundaryViolation(Exception):
    """User-scoped ownership or catalog boundary breach."""


def allowed_stripe_diamond_amounts() -> frozenset[int]:
    from services.stripe_service import DIAMOND_PACKAGES
    return frozenset(int(p['diamonds']) for p in DIAMOND_PACKAGES.values())


def validate_stripe_webhook_credit(user_id: int, diamonds: int) -> None:
    from extensions import db
    from models.user import User

    if user_id <= 0 or diamonds <= 0:
        raise SecurityBoundaryViolation('invalid payment metadata')
    if diamonds not in allowed_stripe_diamond_amounts():
        raise SecurityBoundaryViolation('diamond amount outside catalog')
    if db.session.get(User, user_id) is None:
        raise SecurityBoundaryViolation('user not found')


def resolve_manual_diamond_purchase(amount_usd: int) -> int:
    try:
        amount = int(amount_usd)
    except (TypeError, ValueError) as exc:
        raise SecurityBoundaryViolation('invalid manual purchase amount') from exc
    diamonds = MANUAL_DIAMOND_CATALOG.get(amount)
    if not diamonds:
        raise SecurityBoundaryViolation('invalid manual purchase amount')
    return diamonds


def resolve_custom_diamond_purchase(amount_usd: int) -> int:
    """Resolve diamonds for a custom USD amount within safe bounds."""
    try:
        amount = int(amount_usd)
    except (TypeError, ValueError) as exc:
        raise SecurityBoundaryViolation('invalid custom purchase amount') from exc
    if amount < CUSTOM_MIN_USD or amount > CUSTOM_MAX_USD:
        raise SecurityBoundaryViolation('custom amount out of range')
    return amount * CUSTOM_DIAMONDS_PER_USD


def parse_bank_amount(raw, *, min_value: int = 1) -> int | None:
    """Sanitize bank/market currency amounts."""
    return parse_positive_int(
        raw, min_value=min_value, max_value=ABSOLUTE_MAX_MONEY_DELTA)


def validate_resource_changes(
    changes: dict | None,
    set_fields: dict | None = None,
) -> None:
    """Reject empty, invalid, or extreme resource deltas before ledger mutation."""
    if not changes and not set_fields:
        raise SecurityBoundaryViolation('empty resource mutation')
    if not changes:
        return
    if not isinstance(changes, dict):
        raise SecurityBoundaryViolation('invalid resource changes')
    for res, amount in changes.items():
        if not isinstance(amount, (int, float)):
            raise SecurityBoundaryViolation(f'invalid amount for {res}')
        delta = int(amount)
        if res in ('money', 'bank_balance') and abs(delta) > ABSOLUTE_MAX_MONEY_DELTA:
            raise SecurityBoundaryViolation(f'{res} delta exceeds limit')
        if res == 'diamonds' and abs(delta) > ABSOLUTE_MAX_DIAMOND_DELTA:
            raise SecurityBoundaryViolation('diamonds delta exceeds limit')


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
