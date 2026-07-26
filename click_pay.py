"""
Click.uz orqali to'lov havolasi yaratish.

Ishlashi uchun Click.uz bilan "Merchant" shartnomasi tuzilgan bo'lishi kerak
(https://merchant.click.uz orqali ariza beriladi). Shartnoma tuzilgach sizga:
- merchant_id
- service_id
- secret_key
beriladi - shularni config.py fayliga yozasiz.

To'lov muvaffaqiyatli o'tganini bilish uchun Click serveringizga so'rov yuboradi
(webhook) - buning uchun sizda ochiq (public) HTTPS manzilga ega server bo'lishi kerak.
Bu qism webhook_server.py faylida tayyor turibdi.
"""

from urllib.parse import urlencode
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID


def generate_click_link(amount: int, lead_id: int, return_url: str = "https://t.me") -> str:
    """
    Click Checkout (invoice) havolasini generatsiya qiladi.
    transaction_param sifatida lead_id ishlatiladi - shu orqali webhook
    qaysi mijoz to'laganini aniqlaydi.
    """
    if not CLICK_MERCHANT_ID or not CLICK_SERVICE_ID:
        return (
            "⚠️ Click sozlanmagan. config.py faylida CLICK_MERCHANT_ID va "
            "CLICK_SERVICE_ID ni to'ldiring. (Hozircha test rejimida ishlayapmiz)"
        )

    params = {
        "service_id": CLICK_SERVICE_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": amount,
        "transaction_param": lead_id,
        "return_url": return_url,
    }
    return "https://my.click.uz/services/pay?" + urlencode(params)
