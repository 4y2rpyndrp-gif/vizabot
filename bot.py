"""
Viza konsalting - Telegram sotuv boti.

Oqim:
1. Mijoz botga /start yozadi -> bot 3 ta savol so'raydi (davlat, maqsad, telefon)
2. Lid yaratiladi va eng bo'sh sotuvchiga avtomatik biriktiriladi
3. Sotuvchiga shaxsiy xabar + Nazorat guruhga xabar boradi
4. Sotuvchi /mine, /contacted, /tolov, /yoqotildi buyruqlari orqali ishlaydi
5. FOLLOWUP_HOURS soatdan keyin hali bog'lanilmagan lidlar uchun ogohlantirish boradi
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import ai_seller

# Anketa to'ldirilayotganda /buyruq yozilsa, uni javob deb qabul qilmaslik uchun filtr
def not_a_command(message: Message) -> bool:
    return not (message.text and message.text.startswith("/"))


def not_a_command_or_contact(message: Message) -> bool:
    return bool(message.contact) or not_a_command(message)

import config
import database as db
from click_pay import generate_click_link

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


async def _send_notifications(notify: list):
    """ai_seller qaytargan xabarnomalar ro'yxatini haqiqiy Telegram xabarlariga aylantiradi."""
    for item in notify:
        try:
            if item["type"] == "seller":
                await bot.send_message(item["telegram_id"], item["text"])
            elif item["type"] == "admin" and config.ADMIN_GROUP_ID:
                await bot.send_message(config.ADMIN_GROUP_ID, item["text"])
            elif item["type"] == "client_file":
                if item["file_type"] == "photo":
                    await bot.send_photo(item["client_telegram_id"], item["telegram_file_id"], caption=item.get("caption", ""))
                else:
                    await bot.send_document(item["client_telegram_id"], item["telegram_file_id"], caption=item.get("caption", ""))
        except Exception as e:
            logger.warning(f"Xabarnoma yuborib bo'lmadi: {e}")


@dp.message(F.document | F.photo, StateFilter(None))
async def group_file_upload_handler(message: Message):
    """
    Nazorat guruhida fayl (PDF/rasm) + izoh bilan yuborilsa, uni bilim bazasiga saqlaydi.
    Foydalanish: faylni yuboring, izohiga (caption) shu formatda yozing:
    /fayl <kalit_soz> <tavsif>
    Masalan: /fayl guvohnoma Korxonaning ro'yxatdan o'tganlik guvohnomasi
    """
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return

    caption = (message.caption or "").strip()
    if not caption.startswith("/fayl"):
        return

    parts = caption.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Foydalanish: faylga izoh sifatida yozing:\n/fayl <kalit_soz> <tavsif>")
        return

    keyword = parts[1].lower()
    description = parts[2] if len(parts) > 2 else keyword

    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        file_id = message.photo[-1].file_id
        file_type = "photo"

    db.add_file(keyword, file_id, file_type, description)
    await message.answer(
        f"✅ Fayl bilim bazasiga qo'shildi!\nKalit so'z: «{keyword}»\nTavsif: {description}\n\n"
        f"AI endi mijoz shunga o'xshash narsani so'raganda shu faylni avtomatik yuboradi."
    )


@dp.message(Command("fayllar"))
async def cmd_list_files(message: Message):
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return
    files = db.list_files()
    if not files:
        await message.answer("Fayl kutubxonasi hozircha bo'sh. Faylni yuborib, izohiga /fayl <kalit_soz> <tavsif> deb yozing.")
        return
    lines = ["📎 Fayl kutubxonasi:\n"]
    for f in files:
        lines.append(f"«{f['keyword']}» - {f['description']}")
    lines.append("\nO'chirish uchun: /fayl_ochir <kalit_soz>")
    await message.answer("\n".join(lines))


@dp.message(Command("fayl_ochir"))
async def cmd_delete_file(message: Message):
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Foydalanish: /fayl_ochir <kalit_soz>")
        return
    db.delete_file(parts[1].lower())
    await message.answer(f"✅ «{parts[1]}» fayl kutubxonasidan o'chirildi.")


# ---------------- MIJOZ SUHBATI (FSM holatlari) ----------------

class LeadForm(StatesGroup):
    country = State()
    purpose = State()
    name = State()
    phone = State()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Agar bu odam ro'yxatdagi sotuvchi bo'lsa - unga mijoz anketasi shart emas
    seller = db.get_seller_by_telegram_id(message.from_user.id)
    if seller:
        await message.answer(
            f"Salom, {seller['name']}! Siz sotuvchi sifatida ro'yxatdan o'tgansiz.\n\n"
            "Buyruqlar:\n"
            "/mine - menga biriktirilgan lidlar\n"
            "/contacted <lid_raqami> - bog'landim deb belgilash\n"
            "/tolov <lid_raqami> <summa> - to'lov havolasi yaratish\n"
            "/yoqotildi <lid_raqami> - lidni yo'qotilgan deb belgilash"
        )
        return

    if config.AI_SELLER_ENABLED:
        reply_text, notify = ai_seller.handle_message(
            message.from_user.id,
            message.from_user.username or "",
            "[Yangi mijoz botga /start bilan kirdi. Iliq salomlashib, qaysi davlatga qiziqishini so'ra.]",
        )
        await message.answer(reply_text, reply_markup=ReplyKeyboardRemove())
        await _send_notifications(notify)
        return

    await state.set_state(LeadForm.country)
    await message.answer(
        "Assalomu alaykum! 👋\nViza olish bo'yicha konsalting xizmatimizga xush kelibsiz.\n\n"
        "Qaysi davlatga ish vizasi olmoqchisiz? (Masalan: Germaniya, Chexiya, Polsha va h.k.)",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(F.voice)
async def voice_message_handler(message: Message):
    """Mijoz ovozli xabar yuborsa, iliq tarzda matn yozishni so'raydi."""
    seller = db.get_seller_by_telegram_id(message.from_user.id)
    if seller:
        return
    await message.answer(
        "Voy, uzr bo'lsin-a, hozircha ovozli xabarni eshita olmayapman 😔\n"
        "Noqulay bo'lmasa, savolingizni yozib yuborsangiz - darhol javob beraman!"
    )


@dp.message(StateFilter(None), F.func(not_a_command))
async def ai_chat_handler(message: Message):
    """AI sotuvchi yoqilgan bo'lsa, mijozning har qanday erkin xabari shu yerga tushadi
    (agar u FSM anketasida bo'lmasa va sotuvchi bo'lmasa)."""
    if not config.AI_SELLER_ENABLED:
        return
    seller = db.get_seller_by_telegram_id(message.from_user.id)
    if seller:
        return

    reply_text, notify = ai_seller.handle_message(
        message.from_user.id, message.from_user.username or "", message.text or ""
    )
    await message.answer(reply_text)
    await _send_notifications(notify)


@dp.message(LeadForm.country, F.func(not_a_command))
async def form_country(message: Message, state: FSMContext):
    await state.update_data(country=message.text)
    await state.set_state(LeadForm.purpose)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Turizm"), KeyboardButton(text="Ish")],
            [KeyboardButton(text="O'qish"), KeyboardButton(text="Boshqa")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Maqsadingiz nima?", reply_markup=kb)


@dp.message(LeadForm.purpose, F.func(not_a_command))
async def form_purpose(message: Message, state: FSMContext):
    await state.update_data(purpose=message.text)
    await state.set_state(LeadForm.name)
    await message.answer("Ismingiz va familiyangiz?", reply_markup=ReplyKeyboardRemove())


@dp.message(LeadForm.name, F.func(not_a_command))
async def form_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(LeadForm.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
    )
    await message.answer(
        "Telefon raqamingizni yuboring (tugmani bosing yoki qo'lda yozing):",
        reply_markup=kb,
    )


@dp.message(LeadForm.phone, F.func(not_a_command_or_contact))
async def form_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    data = await state.update_data(phone=phone)
    await state.clear()

    lead_id = db.create_lead(
        client_telegram_id=message.from_user.id,
        client_username=message.from_user.username or "",
        name=data["name"],
        phone=phone,
        country=data["country"],
        purpose=data["purpose"],
    )

    seller = db.assign_lead_round_robin(lead_id)

    await message.answer(
        "Rahmat! ✅ Ma'lumotlaringiz qabul qilindi.\n"
        "Tez orada mutaxassisimiz siz bilan bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )

    if seller:
        client_link = (
            f"@{message.from_user.username}" if message.from_user.username else f"id{message.from_user.id}"
        )
        seller_text = (
            f"🆕 Sizga yangi lid biriktirildi (#{lead_id})\n\n"
            f"👤 Ism: {data['name']}\n"
            f"📞 Tel: {phone}\n"
            f"🌍 Davlat: {data['country']}\n"
            f"🎯 Maqsad: {data['purpose']}\n"
            f"💬 Telegram: {client_link}\n\n"
            f"Bog'langach: /contacted {lead_id}"
        )
        try:
            await bot.send_message(seller["telegram_id"], seller_text)
        except Exception as e:
            logger.warning(f"Sotuvchiga xabar yuborib bo'lmadi: {e}")

        if config.ADMIN_GROUP_ID:
            await bot.send_message(
                config.ADMIN_GROUP_ID,
                f"📥 Yangi lid #{lead_id} → {seller['name']}ga biriktirildi\n"
                f"({data['country']}, {data['purpose']})",
            )
    else:
        if config.ADMIN_GROUP_ID:
            await bot.send_message(
                config.ADMIN_GROUP_ID,
                f"⚠️ Yangi lid #{lead_id} keldi, lekin faol sotuvchi topilmadi! "
                f"/add_seller buyrug'i bilan sotuvchi qo'shing.",
            )


# ---------------- ADMIN: SOTUVCHI QO'SHISH ----------------

@dp.message(Command("add_seller"))
async def cmd_add_seller(message: Message):
    """
    Faqat nazorat guruhida ishlaydi.
    Foydalanish: sotuvchi botga /start yozgandan keyin uning Telegram ID sini
    /myid buyrug'i orqali biladi, so'ng admin guruhda quyidagicha yozadi:
    /add_seller <telegram_id> <ism>
    """
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Foydalanish: /add_seller <telegram_id> <ism>")
        return

    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id butun son bo'lishi kerak.")
        return

    name = parts[2]
    db.add_seller(tg_id, name)
    await message.answer(f"✅ Sotuvchi qo'shildi: {name} (id: {tg_id})")


@dp.message(Command("bilim"))
async def cmd_add_knowledge(message: Message):
    """Faqat nazorat guruhida ishlaydi. Foydalanish: /bilim <fakt matni>
    Bu yerga qo'shilgan har qanday matn AI'ning bilim bazasiga darhol qo'shiladi -
    qayta kod yozish yoki qayta deploy qilish shart emas."""
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return

    fact = message.text.replace("/bilim", "", 1).strip()
    if not fact:
        await message.answer(
            "Foydalanish: /bilim <matn>\n\n"
            "Masalan: /bilim Ofisimiz Toshkent, Chilonzor tumani, Bunyodkor ko'chasi 12-uyda joylashgan"
        )
        return

    db.add_knowledge_fact(fact)
    await message.answer(f"✅ Bilim bazasiga qo'shildi:\n«{fact}»\n\nAI endi shu ma'lumotdan darhol foydalanadi.")


@dp.message(Command("bilimlar"))
async def cmd_list_knowledge(message: Message):
    """Bilim bazasidagi barcha faktlarni ko'rsatadi."""
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return

    facts = db.get_all_knowledge_facts()
    if not facts:
        await message.answer("Bilim bazasi hozircha bo'sh. /bilim <matn> orqali qo'shing.")
        return

    lines = ["📚 Bilim bazasi:\n"]
    for f in facts:
        lines.append(f"#{f['id']}: {f['fact']}")
    lines.append("\nO'chirish uchun: /bilim_ochir <raqam>")
    await message.answer("\n".join(lines))


@dp.message(Command("bilim_ochir"))
async def cmd_delete_knowledge(message: Message):
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /bilim_ochir <raqam>")
        return
    db.delete_knowledge_fact(int(parts[1]))
    await message.answer(f"✅ #{parts[1]} bilim bazasidan o'chirildi.")


@dp.message(Command("savollar"))
async def cmd_unknown_questions(message: Message):
    """Faqat nazorat guruhida ishlaydi - AI bilmagan savollar ro'yxatini ko'rsatadi."""
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return

    questions = db.get_unanswered_questions()
    if not questions:
        await message.answer("Hozircha javobsiz savollar yo'q.")
        return

    lines = ["❓ AI bilmagan savollar:\n"]
    for q in questions[:20]:
        lines.append(f"#{q['id']} (mijoz {q['client_telegram_id']}): {q['question']}")
    lines.append("\nJavob topgach, bilim bazasiga (ai_seller.py) qo'shib, /javoblandi <id> deb belgilang.")
    await message.answer("\n".join(lines))


@dp.message(Command("javoblandi"))
async def cmd_mark_answered(message: Message):
    if config.ADMIN_GROUP_ID and message.chat.id != config.ADMIN_GROUP_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /javoblandi <savol_raqami>")
        return
    db.mark_question_answered(int(parts[1]))
    await message.answer(f"✅ Savol #{parts[1]} javoblandi deb belgilandi.")


@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Sizning Telegram ID: `{message.from_user.id}`", parse_mode="Markdown")


# ---------------- SOTUVCHI BUYRUQLARI ----------------

@dp.message(Command("mine"))
async def cmd_mine(message: Message):
    seller = db.get_seller_by_telegram_id(message.from_user.id)
    if not seller:
        await message.answer("Siz sotuvchi sifatida ro'yxatdan o'tmagansiz.")
        return

    leads = db.get_seller_leads(seller["id"])
    if not leads:
        await message.answer("Sizda hozircha ochiq lidlar yo'q.")
        return

    lines = ["📋 Sizning ochiq lidlaringiz:\n"]
    for l in leads:
        lines.append(
            f"#{l['id']} | {l['name']} | {l['phone']} | {l['country']} | holat: {l['status']}"
        )
    await message.answer("\n".join(lines))


@dp.message(Command("contacted"))
async def cmd_contacted(message: Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /contacted <lid_raqami>")
        return

    lead_id = int(parts[1])
    db.mark_contacted(lead_id)
    await message.answer(f"✅ Lid #{lead_id} 'muloqotda' deb belgilandi.")

    if config.ADMIN_GROUP_ID:
        await bot.send_message(config.ADMIN_GROUP_ID, f"💬 Lid #{lead_id} bilan bog'lanildi.")


@dp.message(Command("tolov"))
async def cmd_tolov(message: Message):
    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Foydalanish: /tolov <lid_raqami> <summa_som>")
        return

    lead_id, amount = int(parts[1]), int(parts[2])
    lead = db.get_lead(lead_id)
    if not lead:
        await message.answer("Bunday lid topilmadi.")
        return

    link = generate_click_link(amount, lead_id)
    db.set_payment_link(lead_id, amount, link)

    await message.answer(
        f"💳 To'lov havolasi (#{lead_id}, {amount:,} so'm):\n{link}\n\n"
        f"Shu havolani mijozga yuboring."
    )

    if config.ADMIN_GROUP_ID:
        await bot.send_message(
            config.ADMIN_GROUP_ID,
            f"💳 Lid #{lead_id} uchun to'lov havolasi yaratildi ({amount:,} so'm).",
        )


@dp.message(Command("yoqotildi"))
async def cmd_lost(message: Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /yoqotildi <lid_raqami>")
        return

    lead_id = int(parts[1])
    db.mark_lost(lead_id)
    await message.answer(f"❌ Lid #{lead_id} 'yo'qotilgan' deb belgilandi.")

    if config.ADMIN_GROUP_ID:
        await bot.send_message(config.ADMIN_GROUP_ID, f"❌ Lid #{lead_id} yo'qotildi.")


# ---------------- AVTOMATIK ESLATMA (background task) ----------------

async def reminder_loop():
    while True:
        try:
            leads = db.get_leads_needing_reminder(config.FOLLOWUP_HOURS)
            for lead in leads:
                db.mark_reminder_sent(lead["id"])
                if config.ADMIN_GROUP_ID:
                    await bot.send_message(
                        config.ADMIN_GROUP_ID,
                        f"⚠️ Diqqat! Lid #{lead['id']} ({lead['name']}) "
                        f"{config.FOLLOWUP_HOURS} soatdan beri bog'lanilmagan!",
                    )
        except Exception as e:
            logger.error(f"Reminder loop xatosi: {e}")

        await asyncio.sleep(600)  # har 10 daqiqada tekshiradi


async def main():
    db.init_db()
    asyncio.create_task(reminder_loop())
    logger.info("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
