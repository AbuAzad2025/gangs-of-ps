"""Economy rules: in-game currency vs real-money diamond purchases."""
from __future__ import annotations

from urllib.parse import quote

# Developer contact (real money — outside the game)
# Developer WhatsApp (Israel number, +972)
SUPPORT_WHATSAPP_NUMBER = '972562150193'
SUPPORT_WHATSAPP_DISPLAY = '+972562150193'
SUPPORT_WHATSAPP_URL = f'https://wa.me/{SUPPORT_WHATSAPP_NUMBER}'

# Developer bank IBAN for donations / transfers
DEVELOPER_IBAN = 'PS54 TNBC 0204 0037 4080 0320 0000 0'


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
