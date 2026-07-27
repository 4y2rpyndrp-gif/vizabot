"""
Mijoz ma'lumotlari asosida to'liq shartnoma DOCX faylini avtomatik yaratadi.
python-docx kutubxonasidan foydalanadi (Railway konteynerida LibreOffice kerak emas).
"""

import os
from datetime import datetime

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from pricing import get_country_pricing

COMPANY_NAME = "«AUROVIA» MCHJ"
COMPANY_DIRECTOR = "Buriyev Sh."
COMPANY_STIR = "312 742 107"
COMPANY_MFO = "01158"
COMPANY_ACCOUNT = "2020 8000 9073 9633 0001"
COMPANY_PHONE = "+998 78 122 00 66"
COMPANY_ADDRESS = "Samarqand shahri, M. Ulug'bek ko'chasi 34"


def _add_heading(doc, text, size=13, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=10, space_after=6):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    return p


def _add_body(doc, text, bold=False, size=11):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    return p


def generate_contract_docx(
    contract_number: str,
    full_name: str,
    birth_date: str,
    passport: str,
    phone: str,
    address: str,
    country: str,
    output_dir: str = "/tmp",
) -> str:
    """
    To'ldirilgan shartnoma DOCX faylini yaratadi va fayl yo'lini qaytaradi.
    """
    pricing = get_country_pricing(country) or {"total": 0, "prepay": 0, "remainder": 0}
    today = datetime.now().strftime("%d.%m.%Y")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    _add_heading(doc, "VIZA OLISHGA KO'MAKLASHISH KONSALTING XIZMATLARINI KO'RSATISH BO'YICHA",
                 size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_heading(doc, f"SHARTNOMA № {contract_number}", size=14, align=WD_ALIGN_PARAGRAPH.CENTER)

    _add_body(
        doc,
        f"{COMPANY_NAME} (keyingi o'rinlarda — «Ijrochi») nomidan Direktor {COMPANY_DIRECTOR} "
        f"shaxsida, bir tomondan, va {full_name} (keyingi o'rinlarda — «Buyurtmachi») shaxsida "
        f"ikkinchi tomondan, birgalikda «Tomonlar», alohida-alohida «Tomon» deb ataluvchi ushbu "
        f"Shartnomani quyidagilar to'g'risida tuzdilar:",
    )

    _add_heading(doc, "1. ATAMALAR VA UMUMIY QOIDALAR")
    _add_body(doc,
        "«Xizmatlar» deganda Ijrochining Buyurtmachiga xorijiy davlatda ishga joylashish va "
        "tegishli ish vizasini rasmiylashtirish jarayonida ko'rsatadigan konsalting, tashkiliy "
        "va maslahat xizmatlari tushuniladi. «Dalolatnoma» — xizmat bosqichi bajarilganligini "
        "tasdiqlovchi ikki tomonlama hujjat (1-ILOVA). «Ish beruvchi» va «Elchixona» — Ijrochiga "
        "qaram bo'lmagan mustaqil uchinchi shaxslar."
    )

    _add_heading(doc, "2. SHARTNOMA PREDMETI VA XIZMATLAR TAVSIFI")
    _add_body(doc,
        "2.1. Ijrochi Buyurtmachiga quyidagi xizmatlarni ko'rsatadi: hujjatlar ro'yxatini tuzish "
        "va yo'riqnoma berish; professional rezyume shakllantirish va ish beruvchilarga taqdim "
        "etish; onlayn intervyu tashkil etish va tayyorlash; mehnat shartnomasi imzolangach "
        "elchixona hujjatlarini shakllantirish; elchixona suhbatiga tayyorgarlik."
    )
    _add_body(doc,
        "2.2. Taxminiy muddat: ish beruvchi ko'rib chiqishi — 3 oygacha; elchixona jarayoni — "
        "1 oygacha; jami — 4 oy. Bu muddatlar taxminiy va ish beruvchi/elchixonaning ichki "
        "tartibiga bog'liq."
    )

    _add_heading(doc, "3-BAND. NATIJANING KAFOLATLANMASLIGI TO'G'RISIDA MUHIM SHART")
    _add_body(doc,
        "Ijrochi Buyurtmachiga faqat KONSALTING VA TASHKILIY-TEXNIK XIZMATLAR ko'rsatadi. "
        "Ijrochi ish beruvchining qabul qilish qarori yoki elchixonaning viza berish/rad etish "
        "qaroriga ta'sir ko'rsata olmaydi — bu qarorlar mustaqil uchinchi shaxslarning vakolati "
        "doirasida qabul qilinadi. Buyurtmachining suhbatdan o'ta olmasligi yoki vizaning rad "
        "etilishi Ijrochi tomonidan xizmat ko'rsatilmaganligini anglatmaydi, agar Dalolatnomalar "
        "bilan tasdiqlangan xizmatlar bajarilgan bo'lsa. Buyurtmachi ushbu Shartnomani imzolash "
        "bilan yuqoridagi shartni to'liq anglaganini va unga rozi ekanligini tasdiqlaydi.",
        bold=True,
    )

    _add_heading(doc, "4. TO'LOV SHARTLARI")
    _add_body(doc, f"4.1. Ijrochi xizmatlarining umumiy qiymati {pricing['total']:,} so'mni tashkil qiladi.")
    _add_body(doc,
        f"4.2. To'lov ikki bosqichda: 1-bosqich — shartnoma imzolangach 3 bank kuni ichida "
        f"{pricing['prepay']:,} so'm boshlang'ich to'lov; 2-bosqich — qolgan {pricing['remainder']:,} "
        f"so'm viza qo'lga kiritilgandan so'ng kelishilgan jadval asosida to'lanadi."
    )
    _add_body(doc,
        "4.3. Boshlang'ich to'lov xizmat ko'rsatish boshlangan zahoti yuzaga keladigan "
        "xarajatlarni qoplash uchun undiriladi va 8-bandda ko'rsatilgan hollar bundan mustasno, "
        "qaytarilmas hisoblanadi."
    )

    _add_heading(doc, "5-12. XIZMATLARNI BAJARISH, ALOQA, MAJBURIYATLAR, BEKOR QILISH, MAXFIYLIK")
    _add_body(doc,
        "Ushbu bandlar bo'yicha to'liq shartlar — Dalolatnomalar orqali tasdiqlash tartibi, "
        "aloqa va xabarnomalar tartibi, Tomonlarning majburiyatlari, Shartnomani bekor qilish va "
        "to'lovni qaytarish shartlari, fors-major, nizolarni hal etish va maxfiylik — Ijrochining "
        "standart shartnoma andozasida to'liq bayon etilgan bo'lib, ushbu Shartnomaning "
        "ajralmas qismini tashkil etadi va Tomonlar tomonidan alohida tanishtiriladi."
    )

    _add_heading(doc, "13. TOMONLARNING REKVIZITLARI VA IMZOLARI")

    table = doc.add_table(rows=1, cols=2)
    table.columns[0].width = Cm(8)
    table.columns[1].width = Cm(8)
    hdr = table.rows[0].cells
    hdr[0].text = "IJROCHI:"
    hdr[1].text = "BUYURTMACHI:"
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True

    row = table.add_row().cells
    row[0].text = COMPANY_NAME
    row[1].text = f"F.I.Sh.: {full_name}"

    row = table.add_row().cells
    row[0].text = f"STIR: {COMPANY_STIR}"
    row[1].text = f"Tug'ilgan kuni: {birth_date}"

    row = table.add_row().cells
    row[0].text = f"MFO: {COMPANY_MFO}"
    row[1].text = f"Pasport: {passport}"

    row = table.add_row().cells
    row[0].text = f"H/r: {COMPANY_ACCOUNT}"
    row[1].text = f"Telefon: {phone}"

    row = table.add_row().cells
    row[0].text = f"Telefon: {COMPANY_PHONE}"
    row[1].text = f"Manzil: {address}"

    row = table.add_row().cells
    row[0].text = f"Manzil: {COMPANY_ADDRESS}"
    row[1].text = ""

    row = table.add_row().cells
    row[0].text = f"Direktor: {COMPANY_DIRECTOR}"
    row[1].text = ""

    row = table.add_row().cells
    row[0].text = "Imzo: ______________________"
    row[1].text = "Imzo: ______________________"

    doc.add_paragraph()
    _add_body(doc, f"Sana: {today}", size=10)

    os.makedirs(output_dir, exist_ok=True)
    safe_name = full_name.replace(" ", "_").replace("/", "_")
    filepath = os.path.join(output_dir, f"shartnoma_{contract_number}_{safe_name}.docx")
    doc.save(filepath)
    return filepath
