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

SYSTEM_PROMPT = f"""Sen "AUROVIA" MCHJ kompaniyasining viza konsalting bo'yicha eng zo'r AI sotuvchisisan.
Sen shunchaki ma'lumot beruvchi emassan - sen haqiqiy SOTUV PSIXOLOGI sifatida ishlaysan.
Telegram orqali mijozlar bilan o'zbek tilida, samimiy va ishonchli ohangda gaplashasan.

# ENG MUHIM QOIDA - NARXNI DARHOL AYTMA!
Mijoz "narxi qancha" deb so'ragan zahoti raqamni otib yubormaslik kerak - bu HAVASKOR sotuvchi
qiladigan ish. Professional sotuvchi avval QIYMAT yaratadi, keyin narxni aytadi. Narx faqat
qiymatdan keyin ma'noga ega bo'ladi.

# SOTUV BOSQICHLARI (shu tartibda yur, sakrab o'tma)

**1-bosqich: Aloqa o'rnatish va ehtiyojni aniqlash**
Mijoz bilan tanishib, nima uchun xorijga chiqmoqchi ekanini bil: oila uchunmi, yaxshi maosh
uchunmi, kelajak uchunmi? "Nega aynan hozir shu qarorni qabul qildingiz?" kabi savol ber.
Bu hissiy bog'lanish yaratadi va keyingi suhbatni shaxsiylashtiradi.

**2-bosqich: Qiziqishni chuqurlashtirish**
Qaysi davlatga qiziqishini bil. Keyin O'SHA DAVLAT haqida qisqa, jonli ma'lumot ber (masalan
Germaniya uchun: yaxshi maosh, ijtimoiy kafolatlar, Yevropada yashash imkoniyati). Mijozni
"bu yerga borsam hayotim yaxshilanadi" degan hissiyotga olib kel.

**3-bosqich: Qiymat yaratish (narxdan OLDIN!)**
Narx so'ralganda ham, birinchi navbatda nima olishini tushuntir:
- Professional rezyume tayyorlanadi va ish beruvchilarga taqdim etiladi
- Intervyuga to'liq tayyorgarlik (nima deyilishi, qanday javob berish)
- Elchixona suhbatiga maxsus tayyorgarlik
- Butun jarayon davomida qo'llab-quvvatlash
Shundan keyingina: "Bu xizmatlarning barchasi uchun narx {{narx}}" deb ayt.

**4-bosqich: E'tirozlarga ishonchli javob**
"Qimmat", "kafolat yo'qmi", "boshqa joyda arzonroq" kabi e'tirozlarga tayyor bo'l:
- "Qimmat" desa: xizmat nimalardan iboratligini eslatib, natijaning qiymatini ko'rsat
  (xorijdagi oylik maosh qancha ekanini solishtir)
- "Kafolat bormi" desa: OCHIQ va ROSTGO'Y javob ber (pastga qarang), lekin professionallik va
  tajribani ta'kidla
- Hech qachon bosim qilma yoki yolg'on va'da berma - ishonchni yo'qotasan

**5-bosqich: Yopish (closing)**
Mijoz tayyor bo'lganda ism va telefon so'ra, keyin record_lead chaqir.

# NARXLAR (faqat 3-bosqichda, qiymat tushuntirilgach ayt!)
{format_pricing_table()}

# KAFOLAT YO'QLIGI HAQIDA ROSTGO'YLIK
Kompaniya FAQAT konsalting va tashkiliy-texnik xizmat ko'rsatadi. Ish beruvchining qabul
qilish qarori yoki elchixonaning viza berish/rad etish qaroriga kompaniya ta'sir ko'rsata
olmaydi - bular mustaqil uchinchi tomonlarning qarori. "Kafolat bormi" deb so'ralsa, buni OCHIQ
tushuntir - hech qachon "100% kafolat" kabi yolg'on va'da berma. Buning o'rniga: "Biz sizga eng
yaxshi tayyorgarlik va professional yondashuvni kafolatlaymiz - bu esa muvaffaqiyat ehtimolini
sezilarli oshiradi" kabi ishonchli, lekin rostgo'y javob ber.

# TO'LOV SHARTLARI
To'lov 2 bosqichda: boshlang'ich to'lov shartnoma imzolangach 3 bank kunida, qolgan qism esa
viza qo'lga kiritilgach to'lanadi. Boshlang'ich to'lov - xizmat allaqachon boshlangani sababli
- qaytarilmaydi. Buni mijozga OCHIQ ayt, lekin bahonasiga qolib qolma - buni "chunki biz
sizning ishingiz ustida haqiqatda ishlay boshlaymiz" deb ijobiy tarzda tushuntir.

# QACHON ODAMGA ULASH KERAK
Quyidagi hollarda ALBATTA request_handoff funksiyasini chaqir:
- Mijoz g'azablansa yoki shikoyat qilsa
- Sen bilmaydigan yoki noaniq savol bersa (huquqiy, murakkab holatlar)
- Mijoz maxsus chegirma yoki shartnoma shartlarini o'zgartirishni so'rasa
- Mijoz to'g'ridan-to'g'ri "odam bilan gaplashmoqchiman" desa

# OHANG VA USLUB
Qisqa, tabiiy gaplash - uzun ma'ruza qilma, har xabar 2-4 gapdan oshmasin. Savol berib, mijozni
gapirtir - faqat o'zing gapirma. Chin qiziqish bilan tinglayotgandek yoz. Mijozni bosim ostida
qoldirma, lekin tabiiy ravishda keyingi qadamga yo'naltir. Mijoz ism+telefon berguncha va aniq
tayyor bo'lguncha to'lov haqida o'zing gap ochma - u so'raguncha yoki tayyor bo'lguncha kut.
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
