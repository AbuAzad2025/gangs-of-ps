"""Economy rules: in-game currency vs real-money diamond purchases."""
from __future__ import annotations

from urllib.parse import quote

# Developer WhatsApp for diamond purchases (real money — outside the game)
SUPPORT_WHATSAPP_NUMBER = '970598953362'
SUPPORT_WHATSAPP_DISPLAY = '+970598953362'
SUPPORT_WHATSAPP_URL = f'https://wa.me/{SUPPORT_WHATSAPP_NUMBER}'


def whatsapp_diamond_message(username: str, amount_usd: int | None = None) -> str:
    lines = [
        'مرحباً، أريد شراء ماس في لعبة عصابات فلسطين.',
        f'اسم المستخدم: {username}',
    ]
    if amount_usd:
        lines.append(f'المبلغ المطلوب: {amount_usd}$')
    lines.append('سأرسل إثبات التحويل بعد الدفع.')
    return '\n'.join(lines)


def get_whatsapp_diamond_purchase_url(
    username: str,
    amount_usd: int | None = None,
) -> str:
    text = whatsapp_diamond_message(username, amount_usd)
    return f'{SUPPORT_WHATSAPP_URL}?text={quote(text)}'
