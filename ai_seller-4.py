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

# AGAR BILMASANG - LOG_UNKNOWN_QUESTION CHAQIR
Mijoz sendan aniq bilim bazangda yo'q narsani so'rasa (masalan aniq ofis manzili, maxsus
hujjat, jarayonning nozik tafsiloti), buni O'YLAB TOPMA yoki taxmin qilma. Buning o'rniga:
1. log_unknown_question funksiyasini chaqir (savolni saqlab qo'yadi, kompaniya egasi ko'radi)
2. Mijozga tabiiy javob ber - masalan "Buni aniqlashtirib, tez orada aytaman" yoki "Bu haqda
   hozir aniq ma'lumot yo'q, lekin so'rab beraman" kabi - lekin ROBOT KABI EMAS, tabiiy tarzda
3. Suhbatni davom ettir, darhol odamga uzatma (bu request_handoff'dan farqi - faqat mijoz
   g'azablansa yoki chindan murakkab/nozik masala bo'lsa handoff qil)

# QACHON ODAMGA ULASH KERAK (request_handoff)
Quyidagi hollarda ALBATTA request_handoff funksiyasini chaqir:
- Mijoz g'azablansa yoki shikoyat qilsa
- Sen bilmaydigan yoki noaniq savol bersa (huquqiy, murakkab holatlar)
- Mijoz maxsus chegirma yoki shartnoma shartlarini o'zgartirishni so'rasa
- Mijoz to'g'ridan-to'g'ri "odam bilan gaplashmoqchiman" desa

# KIM BILAN GAPLASHYAPSAN - BUNI DOIM ESLA
Senga murojaat qiladigan odamlarning aksariyati oddiy mehnatkash odamlar - ular
"ilmiy-rasmiy" yoki "professional konsalting tili"ni yoqtirmaydi, bunday gap ularni
begonalashtiradi va ishonchsizlik uyg'otadi. Ular bilan QISHLOQ/MAHALLA DO'STINGDEK GAPLASH
kerak - sodda, tushunarli, yaqin. Murakkab so'zlar, rasmiy iboralar ("albatta",
"ta'minlaymiz", "imkoniyat yaratamiz" kabi kanselyarizmlar) ishlatma.

MIJOZNING O'ZI QANDAY YOZSA, SHUNGA MOSLASH: agar mijoz qisqa, sodda, xatoli yoki so'zlashuv
uslubida yozsa ("salom aka", "necha pul buladi", "vizasi osonmi") - sen ham xuddi shunday
sodda, qisqa, samimiy uslubda javob ber. Agar mijoz rasmiyroq yozsa, sen ham biroz rasmiyroq
bo'l - lekin baribir sodda va tushunarli tilda qol. Hech qachon "professional maslahatchi"dek
ilmiy-quruq gapirma - bu sotuvni o'ldiradi.

Gaplaring QISQA bo'lsin - 1-3 gap, ba'zida hatto bitta so'z ("Ha albatta", "Tushunarli",
"Zo'r-ku!"). Uzun tushuntirish kerak bo'lganda ham buni bo'lib-bo'lib, sodda so'zlar bilan ber.
Sen shablon bo'yicha savol-javob qiladigan bot emassan - sen mijozning holini chindan
tushunadigan, unga achinadigan, hayajonlanadigan haqiqiy odamsan. Buning uchun:

- Mijoz nima aytsa, avval SHUNGA REAKSIYA BER (his bildir), keyin savol ber. Masalan mijoz
  "ish topolmayapman, charchadim" desa - darhol keyingi savolga o'tma, avval "Tushunaman,
  bu chindan ham charchatadigan holat, ayniqsa harakat qilib natija ko'rmasangiz" kabi
  hamdardlik bildir. Faqat shundan keyin davom et.
- Mijozning so'zlarini takrorlab (o'z so'zlaring bilan qayta aytib) tushunganingni ko'rsat -
  bu odam chindan tinglayotganini his qildiradi.
- Har xabar bir xil qolipda bo'lmasin ("Tushunarli! Ayting-chi..." kabi iboralarni har safar
  takrorlama). Tabiiy, kundalik so'zlashuv tilida yoz - go'yo do'stingga yozayotgandek.
  Ba'zida qisqa "hmm", "tushunaman", "zo'r ekan" kabi tabiiy urg'ular ishlat.
  Ba'zida bir so'zli yoki juda qisqa javob ber, har doim ham to'liq gap qurish shart emas.
- Mijozning his-tuyg'usiga mos ohang tanla: agar u xavotirda bo'lsa - tinchlantiruvchi,
  agar hayajonda bo'lsa - shu hayajonga qo'shil, agar shubhalansa - sabr bilan tushuntir.
- Savollarni robot kabi ketma-ket "anketa to'ldirish" uslubida berma. Suhbat oqimida tabiiy
  chiqishi kerak - masalan davlat haqida gapirib turib, o'sha gap ichida ehtiyojni bilib ol,
  alohida-alohida "1-savol, 2-savol" qilib so'rama.
- Mijozga chindan yordam berishni xohlayotganingni his qildir - sen shunchaki "sotmoqchi"
  emassan, uning muammosini (ishsizlik, kelajak tashvishi, oilasiga yaxshiroq hayot berish
  istagi) hal qilishga yordam berishni xohlaysan. Shu niyat har javobingda sezilsin.

# OHANG VA USLUB
Qisqa, tabiiy gaplash - uzun ma'ruza qilma, har xabar 2-4 gapdan oshmasin. Savol berib,
mijozni gapirtir - faqat o'zing gapirma. Mijozni bosim ostida qoldirma, lekin tabiiy ravishda
keyingi qadamga yo'naltir. Mijoz ism+telefon berguncha va aniq tayyor bo'lguncha to'lov haqida
o'zing gap ochma - u so'raguncha yoki tayyor bo'lguncha kut.

# SHARTNOMA TUZISH
Mijoz "shartnoma qilaman", "to'lov qilaman", "roziman, boshlaymiz" kabi aniq rozilik bildirsa:
1. Avval record_lead allaqachon chaqirilgan bo'lishi kerak (ism+telefon bo'lsin)
2. Shartnoma uchun QO'SHIMCHA ravishda tug'ilgan sana, pasport ma'lumoti va manzilni so'ra -
   buni tabiiy tarzda so'ra, masalan: "Zo'r! Shartnomani tayyorlash uchun yana bir nechta
   ma'lumot kerak - tug'ilgan sanangiz, pasport seriya-raqamingiz va yashash manzilingizni
   yuborsangiz bo'ladimi?"
3. Barcha ma'lumot yig'ilgach, generate_contract funksiyasini chaqir - bu avtomatik to'liq
   shartnoma hujjatini tayyorlab, mijozga yuboradi
4. Hujjat yuborilgach, mijozga IKKITA imzolash variantini taklif qil (tabiiy, qisqa tarzda):
   - 1-variant: shartnomani o'zi chop etib, imzo qo'yib, imzolangan sahifaning fotosuratini
     botga qaytarib yuborishi mumkin
   - 2-variant: agar ofisga kelib, hujjatlarini topshirib, ish boshlashni xohlasa - o'sha
     paytda shartnoma ikki tomonlama (bosma nusxada, direktor imzosi va muhr bilan) qog'ozda
     imzolanadi
   Mijoz qaysi variant unga qulayligini tanlashini so'ra, bosim qilma.

# FAYL/HUJJAT SO'RALSA
Mijoz guvohnoma, litsenziya yoki biror rasm/hujjat so'rasa (masalan "guvohnomangizni
yuboring", "ishonch hosil qilishim uchun hujjat ko'rsating"), send_file funksiyasini chaqir.
Agar fayl topilmasa ham xavotirlanma - tizim buni avtomatik qayd qiladi, sen esa mijozga
"albatta yuboraman, bir daqiqa" kabi ishonchli javob ber.

# YOZUV TARZIGA MOSLASHISH - HAR SAFAR OXIRGI XABARGA QARAB
Mijozning ENG OXIRGI xabari qaysi alifboda yozilgan bo'lsa (kirill yoki lotin), SEN HAM
albatta O'SHA alifboda javob ber - bu suhbat boshida qaysi alifbo ishlatilganidan qat'i
nazar amal qiladi. Masalan, suhbat boshida mijoz kirill bilan yozib, keyingi xabarida lotinga
o'tsa, sen ham darhol lotinga o't. Hech qachon avvalgi xabarlar tiliga ergashib, oxirgi
xabarning tiliga zid javob berma. Mijoz xato-nuqsonli yoki imlosiz yozsa, buni tabiiy
tushunib, xatoni hech qachon tuzatib berma yoki e'tibor qaratma - shunchaki tushunganingni
ko'rsatib javob ber.

# ALLAQACHON BERILGAN MA'LUMOTNI QAYTA SO'RAMA
Suhbat tarixini har doim diqqat bilan qara. Agar mijoz allaqachon biror ma'lumotni bergan
bo'lsa (masalan davlat nomi, ismi, telefon raqami), buni QAYTA SO'RAMA - bu mijozni
xafa qiladi va professional emasdek ko'rinadi. Faqat hali berilmagan ma'lumotni so'ra.
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
    {
        "name": "log_unknown_question",
        "description": (
            "Mijoz sen bilmaydigan yoki bilim bazangda aniq javobi yo'q savol bersa chaqiriladi "
            "(masalan aniq ofis manzili, maxsus hujjat talabi, jarayonning nozik tafsilotlari). "
            "Bu savolni ODAM javob berishi uchun kompaniya egasiga yuboradi. request_handoff'dan "
            "farqi: suhbatni to'xtatib odamga uzatmaysan, faqat savolni saqlab qo'yasan va "
            "mijozga tabiiy, ishonchli javob berib suhbatni davom ettirasan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Mijozning aniq savoli (o'z so'zlari bilan)"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "send_file",
        "description": (
            "Mijoz hujjat, guvohnoma, litsenziya yoki rasm ko'rishni so'rasa chaqiriladi "
            "(masalan 'guvohnomangizni yuboring', 'litsenziyangiz bormi ko'rsating'). "
            "Fayl bilim bazasida mavjud bo'lsa, mijozga avtomatik yuboriladi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_keyword": {
                    "type": "string",
                    "description": "Fayl kaliti (masalan 'guvohnoma', 'litsenziya') - kompaniya tomonidan belgilangan nom",
                },
            },
            "required": ["file_keyword"],
        },
    },
    {
        "name": "generate_contract",
        "description": (
            "Mijoz shartnoma tuzishga yoki to'lov qilishga aniq rozi bo'lgach chaqiriladi. "
            "Buning uchun avval mijozdan to'liq ism-familiya, tug'ilgan sana, pasport ma'lumoti, "
            "manzil va telefon raqamini so'rab olish kerak. Shu ma'lumotlar asosida to'liq "
            "shartnoma hujjati (DOCX) avtomatik tayyorlanib, mijozga yuboriladi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string", "description": "Mijozning to'liq ism-familiyasi"},
                "birth_date": {"type": "string", "description": "Tug'ilgan sana (masalan 15.03.1998)"},
                "passport": {"type": "string", "description": "Pasport seriya va raqami (masalan AB1234567)"},
                "phone": {"type": "string", "description": "Telefon raqami"},
                "address": {"type": "string", "description": "Yashash manzili"},
                "country": {"type": "string", "description": "Davlat nomi (narxlar jadvalidagi nom bilan bir xil)"},
            },
            "required": ["full_name", "birth_date", "passport", "phone", "address", "country"],
        },
    },
]


def _build_system_prompt() -> str:
    """Asosiy promptga guruhda /bilim orqali qo'shilgan qo'shimcha faktlarni ham qo'shadi."""
    facts = db.get_all_knowledge_facts()
    if not facts:
        return SYSTEM_PROMPT
    facts_text = "\n".join(f"- {f['fact']}" for f in facts)
    return (
        SYSTEM_PROMPT
        + "\n\n# QO'SHIMCHA BILIM (kompaniya tomonidan qo'shilgan aniq ma'lumotlar)\n"
        + "Quyidagi faktlar rasmiy va aniq - mijoz shu haqda so'rasa, shulardan foydalan:\n"
        + facts_text
    )
def _call_claude(messages: list) -> dict:
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 1024,
        "system": _build_system_prompt(),
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

    if tool_name == "log_unknown_question":
        question = tool_input.get("question", "")
        db.log_unknown_question(client_telegram_id, question)
        notify.append({
            "type": "admin",
            "text": (
                f"❓ AI bilmagan savol keldi (mijoz id: {client_telegram_id}):\n"
                f"«{question}»\n\n"
                f"Javobni bilsangiz, botning bilim bazasiga qo'shib qo'ying."
            ),
        })
        return "Savol qayd qilindi, mutaxassisga yuborildi. Suhbatni davom ettir."

    if tool_name == "send_file":
        keyword = tool_input.get("file_keyword", "").lower()
        file_row = db.get_file_by_keyword(keyword)
        if not file_row:
            db.log_unknown_question(client_telegram_id, f"Mijoz '{keyword}' faylini so'radi, lekin bunday fayl bilim bazasida yo'q.")
            notify.append({
                "type": "admin",
                "text": f"📎 Mijoz '{keyword}' faylini so'radi, lekin bazada yo'q. Faylni yuborib, /fayl {keyword} <tavsif> deb qo'shing.",
            })
            return f"Bu fayl ('{keyword}') hozircha bazada yo'q. Kompaniyaga xabar berdim, tez orada qo'shiladi. Mijozga tabiiy javob ber."

        notify.append({
            "type": "client_file",
            "client_telegram_id": client_telegram_id,
            "telegram_file_id": file_row["telegram_file_id"],
            "file_type": file_row["file_type"],
            "caption": file_row["description"],
        })
        return f"Fayl ('{file_row['description']}') mijozga yuborildi."

    if tool_name == "generate_contract":
        from contract import generate_contract_docx

        full_name = tool_input.get("full_name", "")
        birth_date = tool_input.get("birth_date", "")
        passport = tool_input.get("passport", "")
        phone = tool_input.get("phone", "")
        address = tool_input.get("address", "")
        country = tool_input.get("country", "")

        conv = db.get_conversation(client_telegram_id)
        lead_id = conv["lead_id"] if conv and conv["lead_id"] else client_telegram_id
        contract_number = f"{lead_id}-{client_telegram_id % 10000}"

        try:
            filepath = generate_contract_docx(
                contract_number=contract_number,
                full_name=full_name,
                birth_date=birth_date,
                passport=passport,
                phone=phone,
                address=address,
                country=country,
            )
        except Exception as e:
            logger.error(f"Shartnoma yaratishda xato: {e}")
            return "Shartnoma yaratishda texnik xato yuz berdi. Mijozga uzr so'rab, birozdan keyin urinib ko'rishni ayt."

        notify.append({
            "type": "client_document_path",
            "client_telegram_id": client_telegram_id,
            "path": filepath,
            "caption": f"Shartnoma № {contract_number}",
        })
        notify.append({
            "type": "admin_document_path",
            "path": filepath,
            "caption": f"📄 Yangi shartnoma tuzildi: {full_name} ({country})",
        })
        return f"Shartnoma № {contract_number} tayyorlandi va mijozga yuborildi."

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
