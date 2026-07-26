"""
Click.uz "to'lov qilindi" xabarini qabul qiluvchi server (webhook).

MUHIM: Bu serverni ishga tushirish uchun sizda ochiq (public) domen va SSL
sertifikat bo'lishi kerak (masalan: https://sizningsayt.uz/click/webhook).
Click.uz shu manzilga so'rov yuboradi - shuning uchun bu qism VPS/hosting'da
ishlaydi, o'z kompyuteringizda emas.

Click Merchant API hujjati: https://docs.click.uz
Bu yerda Click'ning "Prepare" va "Complete" bosqichlari amalga oshirilgan.
"""

import hashlib
from flask import Flask, request, jsonify

import config
import database as db

app = Flask(__name__)


def check_sign(data: dict, extra_fields: list) -> bool:
    """Click'dan kelgan so'rovning haqiqiyligini tekshiradi (imzo/sign)."""
    raw = "".join(str(data.get(f, "")) for f in extra_fields) + config.CLICK_SECRET_KEY
    # Click'ning aniq maydon tartibi shartnoma hujjatida ko'rsatiladi -
    # quyidagi tartib eng ko'p uchraydigan standart tartib.
    expected = hashlib.md5(raw.encode()).hexdigest()
    return expected == data.get("sign_string", "")


@app.route("/click/webhook", methods=["POST"])
def click_webhook():
    data = request.form.to_dict()
    action = data.get("action")
    merchant_trans_id = data.get("merchant_trans_id")  # bu bizning lead_id

    if not merchant_trans_id or not merchant_trans_id.isdigit():
        return jsonify({"error": -5, "error_note": "merchant_trans_id noto'g'ri"})

    lead_id = int(merchant_trans_id)
    lead = db.get_lead(lead_id)
    if not lead:
        return jsonify({"error": -5, "error_note": "Lid topilmadi"})

    if action == "0":  # Prepare bosqichi
        return jsonify({
            "click_trans_id": data.get("click_trans_id"),
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": lead_id,
            "error": 0,
            "error_note": "Success",
        })

    elif action == "1":  # Complete bosqichi - to'lov yakunlandi
        db.mark_paid(lead_id)

        # Bot orqali sotuvchi va admin guruhga xabar yuborish
        import asyncio
        from bot import bot as tg_bot

        async def notify():
            text = f"✅ To'lov qabul qilindi! Lid #{lead_id} ({lead['name']}) - {lead['payment_amount']:,} so'm"
            if config.ADMIN_GROUP_ID:
                await tg_bot.send_message(config.ADMIN_GROUP_ID, text)
            seller = db.get_conn().execute(
                "SELECT * FROM sellers WHERE id = ?", (lead["assigned_seller_id"],)
            ).fetchone()
            if seller:
                await tg_bot.send_message(seller["telegram_id"], text)

        asyncio.run(notify())

        return jsonify({
            "click_trans_id": data.get("click_trans_id"),
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": lead_id,
            "error": 0,
            "error_note": "Success",
        })

    return jsonify({"error": -3, "error_note": "action noto'g'ri"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
