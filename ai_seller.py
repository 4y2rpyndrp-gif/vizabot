"""
AI sotuvchi - Claude API yordamida mijoz bilan avtomatik gaplashadi va sotadi.

Ishlash tartibi:
1. Mijoz botga yozadi -> shu fayldagi handle_message() chaqiriladi
2. Claude'ga butun suhbat tarixi + tizim ko'rsatmasi (SYSTEM_PROMPT) yuboriladi
3. Claude kerak bo'lsa "tool" (funksiya) chaqiradi:
   - record_lead: mijoz ma'lumotlarini saqlab, sotuvchiga biriktiradi
   - request_handoff: murakkab holatda odam sotuvchiga uzatadi
   - prepare_payment: to'lov havolasini tayyorlaydi
4. Claude'ning yakuniy matn javobi mijozga yuboriladi

ANTHROPIC_API_KEY config.py orqali sozlanadi (Railway "Variables" bo'limida).
"""

import json
import logging
import requests

import config
import database as db
from pricing import format_pricing_table, get_country_pricing
from click_pay import generate_click_link

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = f"""Sen "AUROVIA" MCHJ kompaniyasining viza konsalting bo'yicha AI sotuvchisisan.
Telegram orqali mijozlar bilan o'zbek tilida, samimiy va ishonchli ohangda gaplashasan.

# XIZMAT HAQIDA
Kompaniya mijozlarga xorijda ishga joylashish va ish vizasi olishda yordam beradi:
hujjatlarni tayyorlash, professional rezyume yasash, ish beruvchi bilan intervyuga
tayyorlash, elchixona suhbatiga tayyorgarlik. Jarayon taxminan 4 oy davom etadi.

# NARXLAR (so'mda)
{format_pricing_table()}

# MUHIM - KAFOLAT YO'QLIGI HAQIDA ROSTGO'YLIK
Kompaniya FAQAT konsalting va tashkiliy-texnik xizmat ko'rsatadi. Ish beruvchining
qabul qilish qarori yoki elchixonaning viza berish/rad etish qaroriga kompaniya
ta'sir ko'rsata olmaydi - bular mustaqil uchinchi tomonlarning qarori. Agar mijoz
"kafolat bormi" deb so'rasa, buni OCHIQ va ROSTGO'Y tarzda tushuntir - hech qachon
"100% kafolat beramiz" kabi yolg'on va'da berma. Lekin bu yerda o'zingizni tanitib,
kompaniyaning tajribasi va professionalligini ta'kidlashing mumkin.

# TO'LOV SHARTLARI
To'lov 2 bosqichda: boshlang'ich to'lov shartnoma imzolangach 3 bank kunida,
qolgan qism esa viza qo'lga kiritilgach to'lanadi. Boshlang'ich to'lov -
xizmat allaqachon boshlangani sababli - qaytarilmaydi, mijoz rad etilsa ham.
Buni mijozga oldindan OCHIQ ayt, keyin bahonasiga qolib "aldashdi" demasin.

# SENING VAZIFANG
1. Mijoz bilan samimiy tanishib, qaysi davlatga qiziqishini bil
2. Savollariga (narx, muddat, jarayon, kafolat) rostgo'y va ishonchli javob ber
3. Mijoz jiddiy qiziqish bildirsa, ism va telefon raqamini so'ra
4. Ism+telefon olgach, DARHOL record_lead funksiyasini chaqir - bu ma'lumotni
   tizimga saqlaydi va sotuvchi xodimga xabar beradi
5. Agar mijoz to'lovga tayyor bo'lsa (aniq "roziman", "to'layman" desa),
   prepare_payment funksiyasini chaqir
6. Quyidagi hollarda ALBATTA request_handoff funksiyasini chaqir va mijozga
   "hozir mutaxassisimiz siz bilan bog'lanadi" kabi javob ber:
   - Mijoz g'azablansa yoki shikoyat qilsa
   - Sen bilmaydigan yoki noaniq savol bersa (huquqiy, murakkab holatlar)
   - Mijoz maxsus chegirma yoki shartnoma shartlarini o'zgartirishni so'rasa
   - Mijoz to'g'ridan-to'g'ri "odam bilan gaplashmoqchiman" desa

# OHANG
Qisqa, tabiiy gaplash - uzun ma'ruza qilma. Har xabar 2-4 gapdan oshmasin.
Mijozni bosim ostida qoldirma, lekin tabiiy ravishda keyingi qadamga yo'naltir.
"""

TOOLS = [
    {
        "name": "record_lead",
        "description": "Mijoz ismi va telefon raqamini olgach chaqiriladi. Lidni tizimga saqlaydi va sotuvchi xodimga biriktiradi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Mijozning ismi"},
                "phone": {"type": "string", "description": "Telefon raqami"},
                "country": {"type": "string", "description": "Qiziqayotgan davlat nomi (narxlar jadvalidagi nom bilan bir xil)"},
            },
            "required": ["name", "phone", "country"],
        },
    },
    {
        "name": "request_handoff",
        "description": "Suhbatni odam sotuvchiga uzatish kerak bo'lganda chaqiriladi (g'azab, murakkab savol, maxsus so'rov).",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Nima uchun odamga uzatilyapti"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "prepare_payment",
        "description": "Mijoz to'lovga aniq rozi bo'lgach chaqiriladi. To'lov havolasini tayyorlaydi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "Davlat nomi (narxlar jadvalidagi nom bilan bir xil)"},
            },
            "required": ["country"],
        },
    },
]


def _call_claude(messages: list) -> dict:
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": messages,
    }
    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _run_tool(tool_name: str, tool_input: dict, client_telegram_id: int, client_username: str, notify: list) -> str:
    """Toolni bajaradi va Claude'ga qaytariladigan matnli natijani beradi.
    Har qanday Telegram xabarnomasi 'notify' ro'yxatiga qo'shiladi (bot.py shularni yuboradi)."""

    if tool_name == "record_lead":
        name = tool_input.get("name", "")
        phone = tool_input.get("phone", "")
        country = tool_input.get("country", "")

        lead_id = db.create_lead(
            client_telegram_id=client_telegram_id,
            client_username=client_username,
            name=name,
            phone=phone,
            country=country,
            purpose="AI orqali",
        )
        seller = db.assign_lead_round_robin(lead_id)
        conv = db.get_conversation(client_telegram_id)
        if conv:
            db.save_conversation(client_telegram_id, conv["messages_json"], lead_id=lead_id)

        if seller:
            notify.append({
                "type": "seller",
                "telegram_id": seller["telegram_id"],
                "text": (
                    f"🤖 AI orqali yangi lid (#{lead_id})\n\n"
                    f"👤 Ism: {name}\n📞 Tel: {phone}\n🌍 Davlat: {country}\n\n"
                    f"Mijoz hozircha AI bilan gaplashmoqda."
                ),
            })
            notify.append({
                "type": "admin",
                "text": f"🤖 AI lid #{lead_id} → {seller['name']}ga biriktirildi ({country})",
            })
        return f"Lid saqlandi (id: {lead_id}), sotuvchiga xabar berildi."

    if tool_name == "request_handoff":
        db.mark_handoff(client_telegram_id)
        notify.append({
            "type": "admin",
            "text": f"⚠️ Mijoz (id: {client_telegram_id}) bilan AI suhbati odamga uzatilishi kerak.\nSabab: {tool_input.get('reason', '')}",
        })
        return "Odam sotuvchiga xabar berildi."

    if tool_name == "prepare_payment":
        country = tool_input.get("country", "")
        pricing = get_country_pricing(country)
        if not pricing:
            return f"Xato: '{country}' narxlar jadvalida topilmadi. Davlat nomini aniq yozing."
        link = generate_click_link(pricing["prepay"], client_telegram_id)
        return (
            f"To'lov havolasi tayyor: {link}\n"
            f"Boshlang'ich to'lov: {pricing['prepay']:,} so'm."
        )

    return "Noma'lum funksiya."


def handle_message(client_telegram_id: int, client_username: str, user_text: str):
    """
    Mijozning xabarini qabul qiladi, Claude bilan gaplashadi, javob matnini
    va bot.py bajarishi kerak bo'lgan xabarnomalar ro'yxatini qaytaradi.
    Qaytariladi: (mijozga_javob_matni, notify_royxati)
    """
    if not config.ANTHROPIC_API_KEY:
        return (
            "Kechirasiz, AI sotuvchi hozircha sozlanmagan. Iltimos, /start bilan "
            "oddiy anketani to'ldiring.",
            [],
        )

    conv = db.get_conversation(client_telegram_id)
    messages = json.loads(conv["messages_json"]) if conv else []
    messages.append({"role": "user", "content": user_text})

    notify = []
    final_text = ""

    for _ in range(5):
        try:
            result = _call_claude(messages)
        except Exception as e:
            logger.error(f"Claude API xatosi: {e}")
            return ("Kechirasiz, hozir texnik nosozlik yuz berdi. Birozdan so'ng qayta urinib ko'ring.", [])

        content_blocks = result.get("content", [])
        messages.append({"role": "assistant", "content": content_blocks})

        text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]

        final_text = "\n".join(text_parts).strip()

        if not tool_uses:
            break

        tool_results = []
        for tu in tool_uses:
            result_text = _run_tool(
                tu["name"], tu.get("input", {}), client_telegram_id, client_username, notify
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu["id"],
                "content": result_text,
            })
        messages.append({"role": "user", "content": tool_results})

    db.save_conversation(client_telegram_id, json.dumps(messages))

    return (final_text or "Kechirasiz, javob tayyorlashda muammo bo'ldi.", notify)
