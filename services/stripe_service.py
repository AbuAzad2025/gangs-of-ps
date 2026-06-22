"""Optional Stripe checkout — disabled when STRIPE_SECRET_KEY unset."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

DIAMOND_PACKAGES = {
    "5": {"usd": 5, "diamonds": 100},
    "10": {"usd": 10, "diamonds": 250},
    "50": {"usd": 50, "diamonds": 1500},
    "100": {"usd": 100, "diamonds": 4000},
}


def stripe_enabled() -> bool:
    return bool((os.environ.get("STRIPE_SECRET_KEY") or "").strip())


def get_publishable_key() -> str:
    return (os.environ.get("STRIPE_PUBLISHABLE_KEY") or "").strip()


def create_checkout_session(
    user_id: int,
    package_key: str,
    success_url: str,
    cancel_url: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Returns (checkout_url, error_message)."""
    if not stripe_enabled():
        return None, "Stripe not configured"
    pkg = DIAMOND_PACKAGES.get(str(package_key))
    if not pkg:
        return None, "Invalid package"
    try:
        import stripe
    except ImportError:
        return None, "stripe package not installed"
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(pkg["usd"] * 100),
                    "product_data": {
                        "name": f"Gangs of Palestine — {pkg['diamonds']} Diamonds",
                    },
                },
                "quantity": 1,
            }],
            metadata={
                "user_id": str(user_id),
                "diamonds": str(pkg["diamonds"]),
                "package": str(package_key),
            },
            success_url=success_url + "?stripe=success",
            cancel_url=cancel_url + "?stripe=cancel",
        )
        return session.url, None
    except Exception as e:
        return None, str(e)


def handle_webhook_payload(payload: bytes, sig_header: str) -> Dict[str, Any]:
    if not stripe_enabled():
        return {"ok": False, "error": "not configured"}
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET") or ""
    try:
        import stripe
    except ImportError:
        return {"ok": False, "error": "stripe not installed"}
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if event["type"] != "checkout.session.completed":
        return {"ok": True, "ignored": True}
    session = event["data"]["object"]
    meta = session.get("metadata") or {}
    return {
        "ok": True,
        "user_id": int(meta.get("user_id") or 0),
        "diamonds": int(meta.get("diamonds") or 0),
        "session_id": session.get("id"),
    }
